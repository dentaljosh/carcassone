#!/usr/bin/env python3
"""Adjudicate measurement/tiearb2_20260816/READ_RULE.md — TERMINAL-GROUNDED TIE
ARBITRATION, Stage 1b (the funded successor, offline).

Joins the two judges' CRN-paired records on the FRESH tile-tie corpus (deck-seed
band 28100000000..28100000849, root-disjoint from the spent 733-position one):

  * `IF`  = `clair-puct`   — the pricing oracle (DESIGN §5.1 `V^IF`);
  * `ARB` = `tier1-greedy` — the arbitration policy (DESIGN §5.1 `V^ARB`).

and computes, per position, on the parity cross-fit of DESIGN §5.1 (both folds,
symmetrized), at a **selection budget `B`** (DESIGN §5.2):

    sel_B   = sorted(sel)[:B]                       # a strict PREFIX of the
                                                    # 16-world selection half
    a_arb   = argmax_a mean_{j∈sel_B} V^ARB[a,j]    # ARBITRATION (tier1-greedy)
    arb[p]  = mean_{j∈eva} V^IF[a_arb] − mean_{j∈eva} V^IF[champ]   # PRICED BY IF
    a_ora   = argmax_a mean_{j∈sel}   V^IF [a,j]
    ora[p]  = mean_{j∈eva} V^IF[a_ora] − mean_{j∈eva} V^IF[champ]   # THE HEADROOM

⚠️ **Pricing is NEVER clipped** — the budget touches the *selection* half only,
so the cross-fit disjointness of DESIGN §5.1 is preserved exactly at every `B`.
Two arms are adjudicated: **`H` honest** (`B = 16`, Stage 1's arm — the argmax
sees the whole selection half) and **`C` cheap** (`B = B*`, frozen in
`PILOT.json` from cost alone before any fresh-corpus statistic existed). The
whole ladder `B ∈ {1,2,4,8,16}` is reported because the world seeds are
prefix-stable in `M`, so every rung is a *sub-read of records this run already
paid for* — but it is **NEVER a branch input except at `B = 16` and `B = B*`**.

This computes NO estimator that already exists. `parity_indices`, `_sub_mean`,
`crossfit_regret`, `cluster_robust`, `bootstrap_roots`, `aggregate`,
`zero_rates`, `load_plan`, `discover_records`, `pts_to_elo` and `bound_block`
come from `analyze_tiletie`; `paired_ratio_bootstrap`, `sign_check`,
`binom_two_sided`, `rnd_arm_position`, `merge_arb_records`,
`resolve_records_root`, `realized_c_from_records` and the NaN-safe `_ge` come
from `analyze_tiearb` — **both imported UNMODIFIED**.

⚠️ `arb_at_budget(..., B=16)` is **bit-identical** to `analyze_tiearb`'s `arb`:
`parity_indices` already returns an ascending `sel`, so `sorted(sel)[:16] is
sel` elementwise, `_sub_mean` therefore sums in the identical order, the argmax
tie-break `max(range(A), key=(mean, -i))` is the same expression, and the priced
difference is the same expression. `tests/test_tiearb2.py` asserts the identity
exactly (`==`, not `approx`) against `analyze_tiletie.crossfit_regret`.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_tiletie as AT                                       # noqa: E402
import analyze_tiearb as TA                                        # noqa: E402
from analyze_tiearb import _ge                                     # noqa: E402

# ---- READ_RULE §2 committed constants — NOT new numbers --------------------- #
RATIO_BAR = 0.35          # E-FLAT / W-FLAT's own fund bar, verbatim
Z_BAR = 2.0               # likewise theirs (== AT.Z_CONVICTION)
FIXED_DENOM = 0.2803      # the published honest base-rung regret (LADDER_READOUT)
FIXED_DENOM_SE = 0.0708   # ±, reported beside it; NOT propagated (it is a constant)
GBOOT_BAR = 0.05          # G-BOOT: >5% of reps with denominator ≤ 0 voids F
ARMSET_MAX_FRAC = 0.05    # G-ARMSET
DRIFT_BAR = 0.20          # BASELINE_DRIFTED ≡ |rnd_S1 − rnd_S2| ≥ 0.20 pts
RHO_BAR = 1.20            # DEPLOY / the §7.2 cost rule — the N4 trigger currency
BOOT_REPS = AT.BOOTSTRAP_REPS      # 20,000
PARITY_BASE = 1           # Stage 1's convention
M_EXPECTED = 32           # DESIGN §4.5 — load-bearing, must NOT be raised

# ---- DESIGN §5.2 / §7.1 ----------------------------------------------------- #
B_LADDER = (1, 2, 4, 8, 16)
B_HONEST = 16
T_CHAMP = 13.7552         # champion @ k8×1376 = 11,008 sims, SEQUENTIAL, this box
T_PHONE = 1.551           # the shipped phone champion
CHAMP_MOVES_PER_GAME = 72.0        # ~72 champion moves/game (rho_amortized)

# ---- the CORPUS block: everything Stage 1 hard-coded, now parameterised ------ #
#: Stage 1 froze `planned_holdout = 211`, `holdout_completion_frac = n/211`,
#: `N_FLOOR_POOLED = 650` and `N_FLOOR_HOLDOUT = 158` in the source. Stage 1b
#: takes them from the CLI / the plan so the instrument is not corpus-bound.
CORPUS = {
    "n_floor_pooled": 1040,   # DESIGN §6 G-N — the conservative DEFF=1.00 figure
    "n_floor_slice": 400,     # DESIGN §6 G-N — per slice
    "planned_n": None,        # from POSITIONS_PLAN.json unless --planned-n is given
    "target_n": 1400,         # DESIGN §4.3 target build (reported, never a gate)
}

DESIGN_DOC = "measurement/tiearb2_20260816/DESIGN.md"
READ_RULE = "measurement/tiearb2_20260816/READ_RULE.md"
SCHEMA = "carcassonne-tiearb2-readout/v1"

# Stage-1's published read — §4.2(13)'s CROSS-CORPUS comparison. Never a branch input.
STAGE1 = {"arb": 0.2065, "se_arb": 0.0551, "z_arb": 3.75, "F": 0.811,
          "F_fixed": 0.737, "n": 733, "branch": "P-PARTIAL",
          "source": "measurement/tiearb_20260816/READOUT.json"}

BENCH = TA.BENCH          # the E4 autopsy's committed sign-check benchmarks, verbatim

SCOPE_SENTENCE_F_FLAT2 = (
    "This is a FUNDING verdict, not an exclusion — the same scope W-FLAT and Stage 1's "
    "F-FLAT carried. DESIGN §6 states before the run that this design resolves F_fixed "
    "to ±0.30 at 2σ, so a capture below ~0.30 is NOT excluded by this null; the honest "
    "claim is 'terminal-grounded tie arbitration did not fire at a mechanism-sized bar "
    "on a fresh 1,400-position corpus', NOT 'terminal grounding is worth nothing'.")

OPERATIVE_AXIS_STATEMENT = (
    "neither static afterstate functions, nor deeper same-shape search, nor wider "
    "determinization, nor terminal-grounded arbitration expresses the +0.252 pts/ply on "
    "a fresh corpus — while the out-of-family re-pricing says the headroom is real. The "
    "axis has no remaining named mechanism.")

BRANCH_TEXT = {
    "A-DEPLOYABLE": (
        "TERMINAL-GROUNDED TIE ARBITRATION CAPTURES THE HEADROOM, AND IT DOES SO AT A "
        "DEPLOYABLE COST.",
        "On a corpus no programme has ever touched, root-disjoint from the spent one and "
        "powered to resolve the bar, an arm chosen by CRN-paired greedy playouts to "
        "terminal — on worlds disjoint from the ones it is priced on — is worth ≥ 35% of "
        "the oracle headroom at the identical bar and in the identical currency that "
        "E-FLAT (0.00/0.18/0.18) and W-FLAT (0.11/0.26/0.09/0.09/0.30) failed; it convicts "
        "at 2σ; both stratified half-slices agree; AND the same holds at a selection "
        "budget B* whose measured per-tied-ply cost is ≤ 1.20× the champion's per-move "
        "budget. LICENSES (does NOT fund) exactly one thing: a fresh Stage-2 "
        "pre-registration of a deck-paired GAME cell testing the budget-matched arbiter — "
        "and that prereg MAY use the B* cheap arm as its deployable form. The prereg must "
        "(a) carry a matched-wall-clock control arm; (b) carry DESIGN §12.1 verbatim (both "
        "judges are terminal-grounded, so this is not yet a deploy-elo claim); (c) carry "
        "the §5.6 sign-check verdict verbatim if it reads NO CORROBORATION; (d) re-derive "
        "cost against a RUST continuation rather than inheriting rho_wall's python upper "
        "bound. ⛔ It does NOT license a game outside that prereg, a band, a deploy, a "
        "PRODUCTION.yaml change, a leaf term (CL-065 + two dead menus + the 38% reach "
        "bound stand), or a claim id."),
    "A-COSTLY": (
        "THE MECHANISM CAPTURES, BUT NO DEPLOYABLE SHAPE OF IT HAS BEEN DEMONSTRATED.",
        "The honest arm clears every conjunct on a fresh, powered, root-disjoint corpus — "
        "the strongest reading this axis has ever produced — but the budget-legal arm does "
        "not (or no budget in the ladder is legal). LICENSES (does NOT fund) exactly one "
        "thing: a fresh Stage-2 pre-registration of a deck-paired GAME cell, which MUST "
        "solve cost on its own terms and MAY NOT assume the B* arm: DESIGN §7.2 measures "
        "the honest shape at ~7–9× the champion's per-move budget, so a Stage-2 that does "
        "not solve cost is not fundable. Conditions (a)–(d) of A-DEPLOYABLE apply "
        "verbatim. The read-out prints the full B-ladder so the cost/capture crossing is "
        "visible."),
    "B-ANOMALY": (
        "ORDERING ANOMALY — REPORTED, AND IT LICENSES NOTHING.",
        "The cheap arm's selection worlds are a strict SUBSET of the honest arm's, so the "
        "cheap arm cannot be better in expectation; a read in which it passes where the "
        "honest arm fails is a noise signature, not a finding. Both arms are reported in "
        "full, with the B-ladder, AGREE_HC, and the difference arb_H − arb_C with its "
        "paired cluster-robust se. NOTHING CLOSES AND NOTHING IS LICENSED."),
    "P-PARTIAL2": (
        "PRESENT AT THE MECHANISM BAR BUT NOT CONVICTED — UNRESOLVED.",
        "At least one ratio reading clears 0.35 but the conjunction fails (the z bar, or "
        "the two ratio readings straddle, or a slice disagrees). NOTHING CLOSES AND "
        "NOTHING IS LICENSED — in particular this does NOT close the mechanism and does "
        "NOT fund a Stage-2."),
    "F-FLAT2": (
        "THE MECHANISM DID NOT FIRE AT A MECHANISM-SIZED BAR ON A FRESH, POWERED, "
        "ROOT-DISJOINT CORPUS.",
        "Neither arm's ratio reading reaches 0.35 and neither mean is convicted."),
    "U-UNREADABLE": (
        "UNREADABLE — a §3 precondition failed.",
        "Report cost, integrity, and whichever gate failed. Nothing closes, nothing is "
        "licensed, nothing is re-labelled."),
}

ARMS = ("H", "C")


# --------------------------------------------------------------------------- #
# DESIGN §5.2 — the selection-budget arbiter                                    #
# --------------------------------------------------------------------------- #
def arb_at_budget(matrix_arb, matrix_if, sel, eva, champ_pos, B):
    """The budget-`B` arbiter: SELECT on `sorted(sel)[:B]`, PRICE on the FULL `eva`.

    Returns `(arb_value, a_arb)`.

    * **Selection** uses a strict ascending PREFIX of the selection half — the
      prefix-stable CRN world seeds (DESIGN §5.2) make `sel[:B]` exactly the
      worlds a budget-`B` deployment would have drawn.
    * **Pricing is NEVER clipped**: it always uses the whole 16-index evaluation
      half, so selection and evaluation stay disjoint at every `B` and the
      cross-fit non-circularity of DESIGN §5.1 is preserved exactly.
    * At `B = 16` this is `analyze_tiletie.crossfit_regret(matrix_arb, sel, eva,
      champ_pos)`'s own `a_plus` priced by `matrix_if` — the SAME expressions
      Stage 1 evaluates, hence bit-identical (asserted in tests).

    `B` is clamped to `len(sel)`; `B < 1` is a hard error (an arbiter that sees
    no world is not an arbiter).
    """
    if B < 1:
        raise ValueError(f"selection budget B={B} must be >= 1")
    sel_b = sorted(sel)[:B]
    if not sel_b:
        raise ValueError("empty selection half")
    sel_means = [AT._sub_mean(r, sel_b) for r in matrix_arb]
    a_arb = max(range(len(matrix_arb)), key=lambda i: (sel_means[i], -i))
    return (AT._sub_mean(matrix_if[a_arb], eva)
            - AT._sub_mean(matrix_if[champ_pos], eva)), a_arb


# --------------------------------------------------------------------------- #
# per-position assembly                                                        #
# --------------------------------------------------------------------------- #
def build_positions(arms_index: dict, if_by_rid: dict, arb_by_rid: dict, rates: dict,
                    split: dict, rnd_seed: int, b_star: int,
                    parity_base: int = PARITY_BASE):
    """Assemble matrix_if / matrix_arb per position and evaluate every §5 statistic.

    `split` maps `root_id -> "S1"|"S2"`; a root absent from it is counted in
    `counts["unsplit"]` and the position is still analysed (so `G-SPLIT` can
    FAIL loudly rather than the corpus silently shrinking).

    `include_partial_arms=False` semantics are inherited verbatim from
    `analyze_tiletie.build_positions`: a position missing any PLANNED leg in
    either judge is EXCLUDED and counted.
    """
    rows = []
    integ = {j: {"values_a_drift": 0, "seed_drift": 0, "crn_unverified": 0,
                 "checksum_failed": 0, "arm_index_mismatch": 0,
                 "zero_distinct_afterstates": 0} for j in ("if", "arb")}
    cross = {"compared_legs": 0, "crn_cross_mismatch": 0, "seed_cross_mismatch": 0,
             "arm_cross_mismatch": 0, "examples": [],
             # the REALIZED CRN salt, read off the records rather than assumed:
             # DESIGN §0.A withdrew §4.5's `tiearb2-v1` (run_tiletie's
             # WORLD_SEED_SALT is a module constant, and world freshness is
             # carried by the disjoint `rid`s, not by the salt).
             "world_seed_salt_if": set(), "world_seed_salt_arb": set()}
    counts = {"planned": 0, "absent_if": 0, "absent_arb": 0, "armset_mismatch": 0,
              "partial": 0, "champ_arm_absent": 0, "analysed": 0, "unsplit": 0,
              "armset_mismatch_rids": [], "champ_absent_rids": [], "unsplit_roots": []}

    for rid, meta in sorted(arms_index.items()):
        counts["planned"] += 1
        n_arms = len(meta["arms"])
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
        if have_if != have_arb:                      # G-ARMSET
            counts["armset_mismatch"] += 1
            if len(counts["armset_mismatch_rids"]) < 20:
                counts["armset_mismatch_rids"].append(rid)
            continue
        if [r for r in need if r not in if_legs]:    # include_partial_arms=False
            counts["partial"] += 1
            continue

        arm_order = [0] + have_if
        champ_idx = meta.get("champ_arm_index")
        if champ_idx not in arm_order:
            counts["champ_arm_absent"] += 1
            if len(counts["champ_absent_rids"]) < 20:
                counts["champ_absent_rids"].append(rid)
            continue
        champ_pos = arm_order.index(champ_idx)

        # ---- integrity, per judge (analyze_tiletie §2.1 witnesses) -----------
        mats = {}
        for jname, legs in (("if", if_legs), ("arb", arb_legs)):
            ref = legs[have_if[0]]
            va0 = ref["values_a"]
            for r in have_if:
                rec = legs[r]
                if rec["values_a"] != va0:
                    integ[jname]["values_a_drift"] += 1
                if (rec["world_seeds"] != ref["world_seeds"]
                        or rec["playout_seeds"] != ref["playout_seeds"]):
                    integ[jname]["seed_drift"] += 1
                if not rec.get("crn_verified"):
                    integ[jname]["crn_unverified"] += 1
                if rec.get("checksum_ok") is False:
                    integ[jname]["checksum_failed"] += 1
                if (rec.get("pick_a") != meta["arms"][0]
                        or rec.get("pick_b") != meta["arms"][r]):
                    integ[jname]["arm_index_mismatch"] += 1
                if rec.get("distinct_afterstates") == 0:
                    integ[jname]["zero_distinct_afterstates"] += 1
                if rec.get("world_seed_salt") is not None:
                    cross[f"world_seed_salt_{jname}"].add(rec["world_seed_salt"])
            mats[jname] = [list(va0)] + [list(legs[r]["values_b"]) for r in have_if]

        # ---- the CROSS-JUDGE CRN witness (G-CRN) -----------------------------
        for r in have_if:
            irec, arec = if_legs[r], arb_legs[r]
            cross["compared_legs"] += 1
            if list(irec["world_seeds"]) != list(arec["world_seeds"]):
                cross["crn_cross_mismatch"] += 1
                if len(cross["examples"]) < 5:
                    cross["examples"].append(f"{rid} leg{r} world_seeds")
            if list(irec["playout_seeds"]) != list(arec["playout_seeds"]):
                cross["seed_cross_mismatch"] += 1
                if len(cross["examples"]) < 5:
                    cross["examples"].append(f"{rid} leg{r} playout_seeds")
            if (irec.get("pick_a"), irec.get("pick_b")) != (arec.get("pick_a"),
                                                            arec.get("pick_b")):
                cross["arm_cross_mismatch"] += 1

        matrix_if, matrix_arb = mats["if"], mats["arb"]
        m = len(matrix_if[0])

        folds = (AT.parity_indices(m, base=parity_base, swap=False),
                 AT.parity_indices(m, base=parity_base, swap=True))
        a_rnd = TA.rnd_arm_position(rid, len(arm_order), rnd_seed)

        # per-B fold accumulators
        ladder_v = {b: [] for b in B_LADDER}
        ladder_a = {b: [] for b in B_LADDER}
        sec_v = {b: [] for b in B_LADDER}
        arm0_v = {b: [] for b in B_LADDER}
        ora_f, rnd_f, a_oras = [], [], []

        for sel, eva in folds:
            ora, a_ora = AT.crossfit_regret(matrix_if, sel, eva, champ_pos)
            ora_f.append(ora)
            a_oras.append(a_ora)
            rnd_f.append(AT._sub_mean(matrix_if[a_rnd], eva)
                         - AT._sub_mean(matrix_if[champ_pos], eva))
            for b in B_LADDER:
                val, a_arb = arb_at_budget(matrix_arb, matrix_if, sel, eva, champ_pos, b)
                ladder_v[b].append(val)
                ladder_a[b].append(a_arb)
                # SEC-ARB ⚠️ AUDIT-ONLY / CIRCULAR: the SAME pick priced by the ARB
                # judge itself, i.e. exactly the ARB judge's own cross-fit headroom.
                sec_v[b].append(arb_at_budget(matrix_arb, matrix_arb, sel, eva,
                                              champ_pos, b)[0])
                # C-ARM0: the same pick, comparator = arm 0 (the leaf's tie-break).
                arm0_v[b].append(arb_at_budget(matrix_arb, matrix_if, sel, eva, 0, b)[0])

        def sym(xs):
            return (xs[0] + xs[1]) / 2.0

        stratum = meta["stratum"]
        sc = rates["by_stratum"].get(stratum, {"scale_all": 1.0, "scale_strict": 1.0})
        root = meta["root_id"]
        sl = split.get(root)
        if sl is None:
            counts["unsplit"] += 1
            if len(counts["unsplit_roots"]) < 20:
                counts["unsplit_roots"].append(root)

        ora_v, rnd_v = sym(ora_f), sym(rnd_f)
        row = {
            "rid": rid, "root_id": root, "stratum": stratum,
            "rules_profile": meta["rules_profile"],
            "phase_bucket": meta.get("phase_bucket"),
            "capped": bool(meta.get("capped")), "ply": meta.get("ply"),
            "slice": sl,
            "m": m, "n_arms_planned": n_arms, "n_arms_scored": len(arm_order),
            "champ_pos": champ_pos, "arm_order": arm_order,
            "ora": ora_v, "ora_p1": ora_f[0],
            "rnd": rnd_v, "a_rnd": a_rnd, "a_ora_folds": a_oras,
            "scale_all": sc["scale_all"], "scale_strict": sc["scale_strict"],
        }
        # ---- the whole ladder, free (same records) ---------------------------
        for b in B_LADDER:
            row[f"arb_b{b}"] = sym(ladder_v[b])
            row[f"a_arb_b{b}_folds"] = list(ladder_a[b])
        # ---- the two adjudicated arms ---------------------------------------
        for arm, b in (("H", B_HONEST), ("C", b_star)):
            row[f"b_{arm}"] = b
            row[f"arb_{arm}"] = sym(ladder_v[b])
            row[f"arb_{arm}_p1"] = ladder_v[b][0]
            row[f"sec_{arm}"] = sym(sec_v[b])
            row[f"arm0_{arm}"] = sym(arm0_v[b])
            row[f"arb_{arm}_minus_rnd"] = sym(ladder_v[b]) - rnd_v
            row[f"a_arb_{arm}_folds"] = list(ladder_a[b])
            row[f"pickchg_{arm}"] = bool(any(a != champ_pos for a in ladder_a[b]))
            row[f"sel_agree_{arm}"] = bool(
                all(a == o for a, o in zip(ladder_a[b], a_oras)))
        # AGREE_HC — honest and cheap select the SAME arm in BOTH folds.
        row["agree_hc"] = bool(ladder_a[B_HONEST] == ladder_a[b_star])
        rows.append(row)
        counts["analysed"] += 1

    for k in ("world_seed_salt_if", "world_seed_salt_arb"):
        cross[k] = sorted(cross[k])
    denom = counts["analysed"] + counts["armset_mismatch"]
    counts["armset_mismatch_frac"] = (counts["armset_mismatch"] / denom) if denom else 0.0
    counts["armset_frac_note"] = ("denominator = positions where BOTH judges had at least "
                                  "one scored leg, i.e. analysed + armset-mismatched.")
    return rows, integ, cross, counts


# --------------------------------------------------------------------------- #
# READ_RULE §4 — fully mechanical, a PURE function of emitted numbers           #
# --------------------------------------------------------------------------- #
def _le(x, bar):
    """`x <= bar` with NaN treated as NOT satisfying (mirror of `_ge`)."""
    try:
        return bool(x == x and x <= bar)
    except TypeError:
        return False


def decide_branch(arms_stats: dict, slices: dict, rho_wall_bstar,
                  preconditions: dict) -> dict:
    """READ_RULE §3 (preconditions, evaluated FIRST) then §4, verbatim.

        C_z(x)   ≡ z_x ≥ +2.0
        RBAR(x)  ≡ (F_fixed(x) ≥ 0.35) ∧ ((F(x) ≥ 0.35) ∨ G-BOOT(x) fired)
        ANY_R(x) ≡ (F_fixed(x) ≥ 0.35) ∨ ((F(x) ≥ 0.35) ∧ ¬G-BOOT(x))

        INFORMATIVE(s)   ≡ z(ora_s) ≥ +2.0
        BASELINE_DRIFTED ≡ |rnd_S1 − rnd_S2| ≥ 0.20
        C_split(x) ≡ (≥1 slice INFORMATIVE)
                     ∧ ∀ INFORMATIVE s: arb_s(x) ≥ 0
                                        ∨ (BASELINE_DRIFTED ∧ (arb_s(x) − rnd_s) ≥ 0)

        PASS(x)  ≡ C_z(x) ∧ RBAR(x) ∧ C_split(x)
        DEPLOY   ≡ rho_wall(B*) ≤ 1.20
        p = PASS(H) ; q = PASS(C) ∧ DEPLOY
        (T,T) A-DEPLOYABLE · (T,F) A-COSTLY · (F,T) B-ANOMALY
        (F,F) P-PARTIAL2 if (ANY_R(H) ∨ ANY_R(C)) else F-FLAT2

    `arms_stats` = {"H": {"z", "F", "F_fixed", "gboot"}, "C": {...}}.
    `slices`     = {"S1": {"z_ora", "rnd", "arb": {"H":…, "C":…}}, "S2": {...}}.
    NaN never satisfies any conjunct (`_ge` / `_le`). `U-UNREADABLE` pre-empts
    everything. Takes ONLY numbers, so a test can sweep it.
    """
    failed = sorted(k for k, ok in preconditions.items() if not ok)
    base = {"branch": "U-UNREADABLE", "failed_preconditions": failed,
            "arms": {}, "informative_slices": [], "baseline_drifted": None,
            "escape_clause_used": {}, "DEPLOY": None, "p": None, "q": None,
            "failed_conjuncts": {}, "rho_wall_bstar": rho_wall_bstar,
            "read": BRANCH_TEXT["U-UNREADABLE"][1],
            "branch_headline": BRANCH_TEXT["U-UNREADABLE"][0]}
    if failed:
        return base

    informative = [s for s in ("S1", "S2")
                   if _ge((slices.get(s) or {}).get("z_ora"), Z_BAR)]
    r1 = (slices.get("S1") or {}).get("rnd")
    r2 = (slices.get("S2") or {}).get("rnd")
    try:
        d_rnd = abs(r1 - r2)
    except TypeError:
        d_rnd = float("nan")
    drifted = _ge(d_rnd, DRIFT_BAR)

    out_arms, escape, conj = {}, {}, {}
    for x in ARMS:
        a = arms_stats.get(x) or {}
        gb = bool(a.get("gboot"))
        c_z = _ge(a.get("z"), Z_BAR)
        f_ok = _ge(a.get("F"), RATIO_BAR)
        ff_ok = _ge(a.get("F_fixed"), RATIO_BAR)
        rbar = ff_ok and (f_ok or gb)
        any_r = ff_ok or (f_ok and not gb)

        per_slice, used = {}, {}
        for s in ("S1", "S2"):
            if s not in informative:
                per_slice[s] = None            # UNINFORMATIVE — never FAIL
                used[s] = False
                continue
            arb_s = ((slices.get(s) or {}).get("arb") or {}).get(x)
            rnd_s = (slices.get(s) or {}).get("rnd")
            direct = _ge(arb_s, 0.0)
            try:
                corrected = _ge(arb_s - rnd_s, 0.0)
            except TypeError:
                corrected = False
            esc = bool(drifted and corrected)
            per_slice[s] = bool(direct or esc)
            used[s] = bool(per_slice[s] and not direct and esc)
        c_split = bool(informative) and all(v for v in per_slice.values() if v is not None)
        if not informative:
            c_split = False
        passx = bool(c_z and rbar and c_split)

        out_arms[x] = {"C_z": c_z, "RBAR": rbar, "ANY_R": any_r, "C_split": c_split,
                       "F_ge_bar": f_ok, "F_fixed_ge_bar": ff_ok, "g_boot_fired": gb,
                       "slice_ok": per_slice, "PASS": passx}
        escape[x] = used
        conj[x] = _failed_conjuncts_for(out_arms[x], informative, per_slice)

    deploy = _le(rho_wall_bstar, RHO_BAR)
    p = out_arms["H"]["PASS"]
    q = bool(out_arms["C"]["PASS"] and deploy)
    if p and q:
        br = "A-DEPLOYABLE"
    elif p and not q:
        br = "A-COSTLY"
    elif (not p) and q:
        br = "B-ANOMALY"
    elif out_arms["H"]["ANY_R"] or out_arms["C"]["ANY_R"]:
        br = "P-PARTIAL2"
    else:
        br = "F-FLAT2"

    base.update({"branch": br, "failed_preconditions": [], "arms": out_arms,
                 "informative_slices": informative, "baseline_drifted": drifted,
                 "D_rnd": d_rnd, "escape_clause_used": escape, "DEPLOY": deploy,
                 "p": p, "q": q, "failed_conjuncts": conj,
                 "read": BRANCH_TEXT[br][1], "branch_headline": BRANCH_TEXT[br][0]})
    return base


def _failed_conjuncts_for(a: dict, informative: list, per_slice: dict) -> list:
    """READ_RULE §4: a non-passing arm must say EXACTLY which conjunct failed."""
    out = []
    if a["C_z"] is False:
        out.append("C_z (z >= +2.0)")
    if a["RBAR"] is False:
        out.append("RBAR ((F_fixed >= 0.35) and ((F >= 0.35) or G-BOOT fired))")
    if a["C_split"] is False:
        if not informative:
            out.append("C_split (NO slice is INFORMATIVE — z(ora_s) < +2.0 on both, so "
                       "there is nothing resolvable to be consistent about)")
        else:
            bad = [s for s in informative if per_slice.get(s) is False]
            out.append(f"C_split (INFORMATIVE slice(s) {bad} negative on arb_s and, where "
                       f"available, on arb_s - rnd_s)")
    return out


# --------------------------------------------------------------------------- #
# COST — DESIGN §7.1 / §7.2                                                     #
# --------------------------------------------------------------------------- #
def rho_ladder(a_bar, c_tier1) -> dict:
    """`rho_wall(B) = Ā × B × c_tier1 / 13.7552`, plus `rho_amortized` and
    `rho_phone`, over the whole ladder. Returns {} when an input is missing —
    never invents a cost."""
    if a_bar in (None, 0) or c_tier1 in (None, 0):
        return {}
    out = {}
    for b in B_LADDER:
        playouts = float(a_bar) * b * float(c_tier1)
        rho = playouts / T_CHAMP
        out[str(b)] = {
            "B": b,
            "worker_secs_per_tied_ply": playouts,
            "rho_wall": rho,
            "rho_amortized": rho * AT.TIED_TILE_PLIES_PER_GAME / CHAMP_MOVES_PER_GAME,
            "rho_phone": playouts / T_PHONE,
            "legal": bool(rho <= RHO_BAR),
        }
    return out


def b_star_from_cost(a_bar, c_tier1) -> int:
    """DESIGN §7.2, mechanical and COST-ONLY:
    `B* = max{ B ∈ {1,2,4,8,16} : rho_wall(B) ≤ 1.20 }`, else `1`."""
    lad = rho_ladder(a_bar, c_tier1)
    ok = [b for b in B_LADDER if lad.get(str(b), {}).get("legal")]
    return max(ok) if ok else 1


def read_pilot(path: Path) -> dict:
    """`PILOT.json` — the frozen `B*` and the pilot's `c_tier1`. Absent ⇒ nulls."""
    out = {"path": str(path), "present": False, "B_star": None,
           "c_tier1_worker_s_per_playout": None, "g_repro": None, "co_tenant": None,
           "rho_wall_bstar": None, "raw_keys": []}
    if not path.is_file():
        return out
    try:
        d = json.loads(path.read_text())
    except Exception as exc:                          # pragma: no cover - defensive
        out["error"] = f"unreadable: {exc}"
        return out
    out["present"] = True
    out["raw_keys"] = sorted(d)
    cost = d.get("cost") if isinstance(d.get("cost"), dict) else {}
    mech = d.get("mechanical_rule") if isinstance(d.get("mechanical_rule"), dict) else {}
    for src in (d, cost, mech):
        if out["B_star"] is None and src.get("B_star") is not None:
            out["B_star"] = int(src["B_star"])
        if (out["c_tier1_worker_s_per_playout"] is None
                and src.get("c_tier1_worker_s_per_playout") is not None):
            out["c_tier1_worker_s_per_playout"] = float(
                src["c_tier1_worker_s_per_playout"])
        if out["rho_wall_bstar"] is None and src.get("rho_wall_bstar") is not None:
            out["rho_wall_bstar"] = float(src["rho_wall_bstar"])
    out["g_repro"] = d.get("g_repro") or d.get("integrity")
    out["co_tenant"] = d.get("co_tenant")
    return out


def manifest_cost(out_dir: Path, m: int) -> dict:
    """Realized cost from `RUN_MANIFEST_chunk*.json`.

    ⚠️ **Stage 1's `analyze_tiearb.cost_block` reads `leg["elapsed_secs"]` and
    `leg["playouts"]`, but `run_tiletie.launch_legs` writes `wall_secs` and `n`
    (n = POSITIONS in the leg).** The committed Stage-1 READOUT therefore carries
    `c_tier1 = null` and `sum_elapsed_secs = 0.0` from this path. Fixed here: BOTH
    key spellings are read, the derived quantity is labelled with which spelling
    supplied it, and the two are never silently pooled —

      * `elapsed_secs` is Σ per-record worker-seconds (the house `c` definition);
      * `wall_secs × workers` is a wall-clock UPPER BOUND on the same quantity
        (`run_tiletie`'s own smoke prints them as two different numbers).

    Playouts per leg = `playouts` when present, else `n × 2 × m` (each position
    contributes the reference arm and one candidate arm over `m` CRN worlds).
    """
    out = {"source_files": [], "n_legs": 0,
           "sum_elapsed_secs": None, "elapsed_legs": 0,
           "sum_wall_times_workers": None, "wall_legs": 0,
           "playouts": 0, "playouts_source": None,
           "c_from_elapsed_secs": None, "c_from_wall_times_workers": None,
           "key_spelling_seen": [],
           "note": ("Stage 1's cost_block read `elapsed_secs`/`playouts`; "
                    "run_tiletie writes `wall_secs`/`n`. Both spellings are read here "
                    "and reported separately; the records-derived c is preferred.")}
    elapsed, wallw, playouts = 0.0, 0.0, 0
    seen = set()
    pl_src = set()
    for mf in sorted(out_dir.glob("RUN_MANIFEST*.json")):
        try:
            d = json.loads(mf.read_text())
        except Exception:                             # pragma: no cover - defensive
            continue
        out["source_files"].append(mf.name)
        for leg in (d.get("legs") or []):
            if not isinstance(leg, dict):
                continue
            out["n_legs"] += 1
            if leg.get("elapsed_secs") is not None:
                elapsed += float(leg["elapsed_secs"])
                out["elapsed_legs"] += 1
                seen.add("elapsed_secs")
            if leg.get("wall_secs") is not None:
                wallw += float(leg["wall_secs"]) * float(leg.get("workers") or 1)
                out["wall_legs"] += 1
                seen.add("wall_secs")
            if leg.get("playouts") is not None:
                playouts += int(leg["playouts"])
                pl_src.add("playouts")
            elif leg.get("n") is not None:
                playouts += int(leg["n"]) * 2 * int(m or M_EXPECTED)
                pl_src.add("n x 2 x m")
    out["key_spelling_seen"] = sorted(seen)
    out["playouts"] = playouts or None
    out["playouts_source"] = " + ".join(sorted(pl_src)) or None
    if out["elapsed_legs"]:
        out["sum_elapsed_secs"] = elapsed
        if playouts:
            out["c_from_elapsed_secs"] = elapsed / playouts
    if out["wall_legs"]:
        out["sum_wall_times_workers"] = wallw
        if playouts:
            out["c_from_wall_times_workers"] = wallw / playouts
    return out


# --------------------------------------------------------------------------- #
# aggregation                                                                  #
# --------------------------------------------------------------------------- #
STAT_KEYS = (
    ("arb_H", "arb_H"), ("arb_C", "arb_C"),
    ("ora", "ora"), ("rnd", "rnd"),
    ("arb_H_minus_rnd", "arb_H_minus_rnd"), ("arb_C_minus_rnd", "arb_C_minus_rnd"),
    ("arm0_H", "arm0_H"), ("arm0_C", "arm0_C"),
    ("sec_H", "sec_H"), ("sec_C", "sec_C"),
    ("arb_H_parity_base1", "arb_H_p1"), ("arb_C_parity_base1", "arb_C_p1"),
    ("ora_parity_base1", "ora_p1"),
)


def agg_block(rows: list, seed: int) -> dict:
    out = {"n": len(rows), "n_roots": len({r["root_id"] for r in rows})}
    out["positions_per_root"] = (out["n"] / out["n_roots"]) if out["n_roots"] else None
    for name, key in STAT_KEYS:
        out[f"{name}_all"] = AT.aggregate(rows, key, "scale_all",
                                          n_boot=BOOT_REPS, seed=seed)
        out[f"{name}_discriminable"] = AT.aggregate(rows, key, None,
                                                    n_boot=BOOT_REPS, seed=seed)
    return out


def ladder_block(rows: list, ora_mean) -> dict:
    """The B-ladder — cluster-robust only (no bootstrap): DESIGN §5.5 asks for
    `arb`, `z`, `F`, `F_fixed`, and the rho's. ⛔ NEVER a branch input except at
    `B = 16` and `B = B*`."""
    roots = [r["root_id"] for r in rows]
    out = {}
    for b in B_LADDER:
        vals = [r[f"arb_b{b}"] * r["scale_all"] for r in rows]
        mean, se, n, g = AT.cluster_robust(vals, roots)
        out[str(b)] = {
            "B": b, "n": n, "n_roots": g, "arb": mean, "se": se,
            "z": (mean / se) if (se and se == se and se > 0) else float("nan"),
            "F": (mean / ora_mean) if ora_mean else float("nan"),
            "F_fixed": mean / FIXED_DENOM,
        }
    return out


def cut_blocks(rows: list) -> dict:
    """Per-phase / per-arm-count / capped cuts. ⚠️ NEVER a branch input."""
    cuts = defaultdict(lambda: {"arb": [], "ora": [], "roots": []})
    for r in rows:
        for nm in (f"phase:{r['phase_bucket']}",
                   f"arms:{r['n_arms_scored']}",
                   f"stratum:{r['stratum']}",
                   f"profile:{r['rules_profile']}",
                   "capped_only" if r["capped"] else "uncapped_only"):
            cuts[nm]["arb"].append(r["arb_H"] * r["scale_all"])
            cuts[nm]["ora"].append(r["ora"] * r["scale_all"])
            cuts[nm]["roots"].append(r["root_id"])
    out = {}
    for nm, d in sorted(cuts.items()):
        ma, sa, n, g = AT.cluster_robust(d["arb"], d["roots"])
        mo, so, _, _ = AT.cluster_robust(d["ora"], d["roots"])
        out[nm] = {"n": n, "n_roots": g,
                   "arb": ma, "se_arb": sa, "z_arb": (ma / sa) if sa else float("nan"),
                   "ora": mo, "se_ora": so, "z_ora": (mo / so) if so else float("nan"),
                   "F_point": (ma / mo) if mo else float("nan"),
                   "F_fixed_point": ma / FIXED_DENOM}
    return out


def composition(rows: list) -> dict:
    out = {}
    for sl in ("pooled", "S1", "S2"):
        sub = rows if sl == "pooled" else [r for r in rows if r["slice"] == sl]
        d = {"n": len(sub), "n_roots": len({r["root_id"] for r in sub}),
             "by_stratum": defaultdict(int), "by_profile": defaultdict(int),
             "by_phase": defaultdict(int), "by_arm_count": defaultdict(int), "capped": 0}
        for r in sub:
            d["by_stratum"][r["stratum"]] += 1
            d["by_profile"][r["rules_profile"]] += 1
            d["by_phase"][str(r["phase_bucket"])] += 1
            d["by_arm_count"][str(r["n_arms_scored"])] += 1
            d["capped"] += 1 if r["capped"] else 0
        d["positions_per_root"] = (d["n"] / d["n_roots"]) if d["n_roots"] else None
        out[sl] = {k: (dict(v) if isinstance(v, defaultdict) else v) for k, v in d.items()}
    return out


# --------------------------------------------------------------------------- #
# MAIN                                                                          #
# --------------------------------------------------------------------------- #
DEFAULT_ARB_ROOTS = ["/mnt/c/carc-shared/tiearb2_20260816/tier1-greedy"]
DEFAULT_IF_ROOT = "/mnt/c/carc-shared/tiearb2_20260816/clair-puct"
RUN_DIR = REPO / "measurement/tiearb2_20260816"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--if-records", default=DEFAULT_IF_ROOT,
                    help="clair-puct (IF) records root")
    ap.add_argument("--arb-records", action="append", default=None,
                    help="repeatable; roots holding tier1-greedy (ARB) records")
    ap.add_argument("--plan-dir", default=str(RUN_DIR / "corpus/positions"))
    ap.add_argument("--full-supply-plan", default=None,
                    help="full-supply POSITIONS_PLAN.json for the analytic-zero rates; "
                         "defaults to --plan-dir's own plan")
    ap.add_argument("--split", default=str(RUN_DIR / "SPLIT.json"),
                    help="the DESIGN §5.4 stratified half-split (split_tiearb2.py)")
    ap.add_argument("--pilot", default=str(RUN_DIR / "PILOT.json"))
    ap.add_argument("--out-dir", default=str(RUN_DIR))
    # ---- the CORPUS block (Stage 1 hard-coded these) ------------------------ #
    ap.add_argument("--n-floor-pooled", type=int, default=CORPUS["n_floor_pooled"])
    ap.add_argument("--n-floor-slice", type=int, default=CORPUS["n_floor_slice"])
    ap.add_argument("--planned-n", type=int, default=None,
                    help="planned analysed positions (default: the plan's n_positions)")
    ap.add_argument("--target-n", type=int, default=CORPUS["target_n"])
    # ---- the two arms ------------------------------------------------------- #
    ap.add_argument("--b-star", type=int, default=None, choices=list(B_LADDER),
                    help="override PILOT.json's frozen B* (a DEVIATION; recorded)")
    ap.add_argument("--a-bar", type=float, default=None,
                    help="mean arm count Ā; default: the plan's mean_arms")
    ap.add_argument("--c-tier1", type=float, default=None,
                    help="override the pilot's worker-s/playout (a DEVIATION; recorded)")
    ap.add_argument("--rho-source", choices=("pilot", "records"), default="pilot",
                    help="which c_tier1 feeds the DEPLOY conjunct. READ_RULE §2 defines "
                         "rho_wall with the PILOT's c (B* was frozen from it), so `pilot` "
                         "is the default; `records` is a reported sensitivity.")
    ap.add_argument("--boot-seed", type=int, default=20260816)
    ap.add_argument("--rnd-seed", type=int, default=20260816)
    ap.add_argument("--parity-base", type=int, choices=(0, 1), default=PARITY_BASE)
    ap.add_argument("--sigma-game", type=float, default=AT.SIGMA_GAME_WALLED,
                    help="the corpus is 100%% `walled` (DESIGN §4.2)")
    a = ap.parse_args(argv)
    if not a.arb_records:
        a.arb_records = list(DEFAULT_ARB_ROOTS)
    if a.full_supply_plan is None:
        a.full_supply_plan = str(Path(a.plan_dir) / "POSITIONS_PLAN.json")
    return a


def load_split(path) -> tuple:
    """SPLIT.json -> ({root: "S1"|"S2"}, the raw document)."""
    doc = json.loads(Path(path).read_text())
    m = {}
    for sl in ("S1", "S2"):
        for root in doc.get(f"{sl}_roots", []):
            if root in m:
                raise SystemExit(f"REFUSING: root {root} appears in BOTH slices of {path}")
            m[root] = sl
    return m, doc


def build_readout(args) -> dict:
    plan_bundle = AT.load_plan(args.plan_dir)
    arms = plan_bundle["arms"]
    rates = AT.zero_rates(plan_bundle, args.full_supply_plan)
    split_map, split_doc = load_split(args.split)

    pilot = read_pilot(Path(args.pilot))
    a_bar = args.a_bar
    if a_bar is None:
        a_bar = plan_bundle["plan"].get("mean_arms")
    c_pilot = args.c_tier1 if args.c_tier1 is not None else pilot[
        "c_tier1_worker_s_per_playout"]

    b_star = args.b_star if args.b_star is not None else pilot["B_star"]
    b_star_source = ("--b-star (DEVIATION: PILOT.json's frozen value overridden)"
                     if args.b_star is not None else
                     "PILOT.json::B_star (frozen from cost alone before any "
                     "fresh-corpus statistic existed)")
    b_star_derived = b_star_from_cost(a_bar, c_pilot)
    if b_star is None:
        b_star = b_star_derived
        b_star_source = ("DERIVED here by the DESIGN §7.2 rule from Ā and the pilot's "
                         "c_tier1 — ⚠️ PILOT.json carried no `B_star`")
    if b_star not in B_LADDER:
        raise SystemExit(f"REFUSING: B* = {b_star} is not on the committed ladder "
                         f"{B_LADDER}")

    if_root = TA.resolve_records_root(args.if_records)
    if if_root.name != "clair-puct" and (Path(args.if_records) / "clair-puct").is_dir():
        if_root = Path(args.if_records) / "clair-puct"
    if_by_rid, if_present, if_not_ok = AT.discover_records(if_root)
    arb_by_rid, arb_present, arb_not_ok, arb_roots = TA.merge_arb_records(args.arb_records)

    rows, integ, cross, counts = build_positions(
        arms, if_by_rid, arb_by_rid, rates, split_map,
        rnd_seed=args.rnd_seed, b_star=b_star, parity_base=args.parity_base)
    if not rows:
        raise SystemExit("REFUSING: no position had BOTH judges' complete records.")

    slices_rows = {"S1": [r for r in rows if r["slice"] == "S1"],
                   "S2": [r for r in rows if r["slice"] == "S2"]}
    blocks = {"pooled": agg_block(rows, args.boot_seed)}
    for s in ("S1", "S2"):
        blocks[s] = agg_block(slices_rows[s], args.boot_seed) if slices_rows[s] else None

    P = blocks["pooled"]
    ora_mean = P["ora_all"]["mean"]
    z_ora = P["ora_all"]["z"]

    # ---- the primary block, per arm, per slice ------------------------------ #
    primary = {}
    for sl in ("pooled", "S1", "S2"):
        blk = blocks[sl]
        sub = rows if sl == "pooled" else slices_rows[sl]
        if not blk:
            primary[sl] = None
            continue
        d = {"n": blk["n"], "n_roots": blk["n_roots"],
             "positions_per_root": blk["positions_per_root"],
             "ora": blk["ora_all"]["mean"], "se_ora": blk["ora_all"]["se_cluster"],
             "z_ora": blk["ora_all"]["z"],
             "ora_boot_lo": blk["ora_all"]["boot_lo"],
             "ora_boot_hi": blk["ora_all"]["boot_hi"],
             "rnd": blk["rnd_all"]["mean"], "se_rnd": blk["rnd_all"]["se_cluster"],
             "z_rnd": blk["rnd_all"]["z"],
             "arms": {}}
        roots_v = [r["root_id"] for r in sub]
        den = [r["ora"] * r["scale_all"] for r in sub]
        for x in ARMS:
            a = blk[f"arb_{x}_all"]
            num = [r[f"arb_{x}"] * r["scale_all"] for r in sub]
            F_med, F_lo, F_hi, F_fin, g_boot = TA.paired_ratio_bootstrap(
                num, den, roots_v, n_boot=BOOT_REPS, seed=args.boot_seed)
            F = ((a["mean"] / d["ora"]) if (d["ora"] not in (None, 0)
                                            and a["mean"] is not None)
                 else float("nan"))
            d["arms"][x] = {
                "B": (B_HONEST if x == "H" else b_star),
                "arb": a["mean"], "se": a["se_cluster"], "z": a["z"],
                "boot_lo": a["boot_lo"], "boot_hi": a["boot_hi"],
                "sd_positions": a["sd_positions"],
                "F": F, "F_lo": F_lo, "F_hi": F_hi, "F_boot_median": F_med,
                "F_boot_finite_reps": F_fin,
                "G-BOOT": g_boot,
                "G-BOOT_fired": bool(g_boot == g_boot and g_boot > GBOOT_BAR),
                "F_fixed": (a["mean"] / FIXED_DENOM if a["mean"] is not None
                            else float("nan")),
                "F_fixed_lo": (a["boot_lo"] / FIXED_DENOM
                               if a["boot_lo"] is not None else float("nan")),
                "F_fixed_hi": (a["boot_hi"] / FIXED_DENOM
                               if a["boot_hi"] is not None else float("nan")),
                "arb_minus_rnd": blk[f"arb_{x}_minus_rnd_all"]["mean"],
            }
        primary[sl] = d

    # ---- cost --------------------------------------------------------------- #
    m_realized = sorted({r["m"] for r in rows})
    c_records = TA.realized_c_from_records(arb_by_rid, {r["rid"] for r in rows})
    c_rec = c_records.get("c_tier1_worker_s_per_playout")
    mani = manifest_cost(Path(args.out_dir), m_realized[0] if m_realized else M_EXPECTED)
    c_branch = c_pilot if args.rho_source == "pilot" else c_rec
    lad_pilot = rho_ladder(a_bar, c_pilot)
    lad_rec = rho_ladder(a_bar, c_rec)
    lad_branch = lad_pilot if args.rho_source == "pilot" else lad_rec
    rho_bstar = lad_branch.get(str(b_star), {}).get("rho_wall")
    if rho_bstar is None and pilot["rho_wall_bstar"] is not None:
        rho_bstar = pilot["rho_wall_bstar"]

    cost = {
        "A_bar_mean_arms": a_bar,
        "A_bar_source": ("--a-bar" if args.a_bar is not None
                         else f"{args.plan_dir}/POSITIONS_PLAN.json::mean_arms"),
        "c_tier1_pilot": c_pilot,
        "c_tier1_realized_from_records": c_rec,
        "c_tier1_from_run_manifests": mani,
        "c_tier1_used_for_the_branch": c_branch,
        "c_tier1_branch_source": args.rho_source,
        "t_champ_secs": T_CHAMP, "t_phone_secs": T_PHONE,
        "rho_bar": RHO_BAR,
        "B_star": b_star, "B_star_source": b_star_source,
        "B_star_rederived_from_cost_rule": b_star_derived,
        "B_star_matches_cost_rule": bool(b_star == b_star_derived),
        "ladder_from_pilot_c": lad_pilot,
        "ladder_from_realized_c": lad_rec,
        "rho_wall_bstar": rho_bstar,
        "pilot": pilot,
        "note": ("DESIGN §7.1's declared bias: rho_wall OVERSTATES the deployable cost "
                 "(c_tier1 is the pure-python v1-object-leaf continuation; t_champ is the "
                 "cython production search), so the bar is applied to the pessimistic "
                 "number. READ_RULE §2 defines rho_wall with the PILOT's c_tier1, which is "
                 "the c that froze B* before any fresh-corpus statistic existed; the "
                 "realized-c ladder is reported beside it as a sensitivity and is NOT a "
                 "branch input unless --rho-source records is passed (a DEVIATION)."),
    }

    # ---- preconditions (READ_RULE §3) --------------------------------------- #
    analysed_roots = {r["root_id"] for r in rows}
    split_roots = set(split_map)
    s1r = {r for r in analysed_roots if split_map.get(r) == "S1"}
    s2r = {r for r in analysed_roots if split_map.get(r) == "S2"}
    g_split = bool(counts["unsplit"] == 0
                   and not (s1r & s2r)
                   and analysed_roots <= split_roots
                   and split_doc.get("balance_ok") is True
                   and all(c.get("balanced") for c in
                           (split_doc.get("cells") or {}).values())
                   and len(split_doc.get("cells") or {}) == 18)
    pre = {
        "G-CRN": bool(cross["crn_cross_mismatch"] == 0 and cross["seed_cross_mismatch"] == 0
                      and integ["arb"]["crn_unverified"] == 0
                      and integ["arb"]["checksum_failed"] == 0
                      and integ["if"]["crn_unverified"] == 0
                      and integ["if"]["checksum_failed"] == 0),
        "G-ARM": bool(integ["if"]["arm_index_mismatch"] == 0
                      and integ["arb"]["arm_index_mismatch"] == 0
                      and cross["arm_cross_mismatch"] == 0),
        "G-VA": bool(integ["if"]["values_a_drift"] == 0
                     and integ["arb"]["values_a_drift"] == 0),
        "G-ARMSET": bool(counts["armset_mismatch_frac"] <= ARMSET_MAX_FRAC),
        "G-SPLIT": g_split,
        "G-N": bool(len(rows) >= args.n_floor_pooled
                    and len(slices_rows["S1"]) >= args.n_floor_slice
                    and len(slices_rows["S2"]) >= args.n_floor_slice),
        "G-DENOM": bool(ora_mean is not None and ora_mean > 0
                        and z_ora == z_ora and z_ora >= Z_BAR),
    }

    # ---- adjudication (READ_RULE §4) ---------------------------------------- #
    arms_stats = {x: {"z": primary["pooled"]["arms"][x]["z"],
                      "F": primary["pooled"]["arms"][x]["F"],
                      "F_fixed": primary["pooled"]["arms"][x]["F_fixed"],
                      "gboot": primary["pooled"]["arms"][x]["G-BOOT_fired"]}
                  for x in ARMS}
    slice_stats = {}
    for s in ("S1", "S2"):
        pr = primary.get(s)
        slice_stats[s] = ({"z_ora": pr["z_ora"], "rnd": pr["rnd"],
                           "arb": {x: pr["arms"][x]["arb"] for x in ARMS}}
                          if pr else
                          {"z_ora": float("nan"), "rnd": float("nan"),
                           "arb": {x: float("nan") for x in ARMS}})
    adj = decide_branch(arms_stats, slice_stats, rho_bstar, pre)
    if adj["branch"] == "F-FLAT2":
        adj["mandatory_scope_sentence"] = SCOPE_SENTENCE_F_FLAT2
        adj["operative_axis_statement"] = OPERATIVE_AXIS_STATEMENT
        ffhi = primary["pooled"]["arms"]["H"]["F_fixed_hi"]
        adj["rider_35pct_capture_excluded"] = bool(ffhi == ffhi and ffhi < RATIO_BAR)
        adj["rider_contradicts_stage1"] = True

    # ---- companions --------------------------------------------------------- #
    sign = {}
    for x in ARMS:
        shim = [{"arb": r[f"arb_{x}"], "scale_all": r["scale_all"],
                 "pickchg": r[f"pickchg_{x}"]} for r in rows]
        sign[x] = TA.sign_check(shim, primary["pooled"]["arms"][x]["arb"])

    pickchg = {x: {
        "frac_pick_changed": AT._mean([1.0 if r[f"pickchg_{x}"] else 0.0 for r in rows]),
        "frac_selector_agreement": AT._mean(
            [1.0 if r[f"sel_agree_{x}"] else 0.0 for r in rows]),
        "frac_pick_changed_fold1": AT._mean(
            [1.0 if r[f"a_arb_{x}_folds"][0] != r["champ_pos"] else 0.0 for r in rows]),
        "frac_pick_changed_fold2": AT._mean(
            [1.0 if r[f"a_arb_{x}_folds"][1] != r["champ_pos"] else 0.0 for r in rows]),
    } for x in ARMS}

    # arb_H − arb_C with its PAIRED cluster-robust se (B-ANOMALY's mandatory print)
    d_vals = [(r["arb_H"] - r["arb_C"]) * r["scale_all"] for r in rows]
    dm, dse, dn, dg = AT.cluster_robust(d_vals, [r["root_id"] for r in rows])
    arm_diff = {"mean": dm, "se_cluster_paired": dse, "n": dn, "n_roots": dg,
                "z": (dm / dse) if (dse and dse == dse and dse > 0) else float("nan"),
                "note": "paired within position (same records, same folds), so the se is "
                        "the se OF THE DIFFERENCE, not of two independent means."}

    ladders = {"pooled": ladder_block(rows, ora_mean)}
    for s in ("S1", "S2"):
        if slices_rows[s]:
            ladders[s] = ladder_block(slices_rows[s], primary[s]["ora"])

    # ---- the bound chain ----------------------------------------------------- #
    def bound(a, label):
        if a is None or a.get("mean") is None:
            return None
        return AT.bound_block(a["mean"] * AT.FULLSET_EXTRAP,
                              (a["boot_lo"] or 0.0) * AT.FULLSET_EXTRAP,
                              (a["boot_hi"] or 0.0) * AT.FULLSET_EXTRAP,
                              args.sigma_game, label)

    se_H = primary["pooled"]["arms"]["H"]["se"]
    two_sigma = 2 * se_H if (se_H and se_H == se_H) else float("nan")
    n_for_pm = (len(rows) * (two_sigma / (RATIO_BAR * FIXED_DENOM)) ** 2
                if two_sigma == two_sigma and two_sigma > 0 else None)

    # ---- §4.2(13) the CROSS-CORPUS Stage-1 contrast (never a branch input) --- #
    arb_H = primary["pooled"]["arms"]["H"]["arb"]
    try:
        d_arb = arb_H - STAGE1["arb"]
        se_d = (se_H ** 2 + STAGE1["se_arb"] ** 2) ** 0.5
        z_d = d_arb / se_d if se_d else float("nan")
    except TypeError:                                  # pragma: no cover - defensive
        d_arb = se_d = z_d = float("nan")
    stage1_cmp = {
        "stage1": dict(STAGE1),
        "here_arb_H": arb_H, "here_se": se_H,
        "here_F_fixed_H": primary["pooled"]["arms"]["H"]["F_fixed"],
        "difference_arb": d_arb, "se_of_difference": se_d, "z_of_difference": z_d,
        "difference_F_fixed": (primary["pooled"]["arms"]["H"]["F_fixed"]
                               - STAGE1["F_fixed"]),
        "label": "⚠️ CROSS-CORPUS contrast — subject to the CLAUDE.md cross-band ~1.5–2× "
                 "humility rule (the fresh corpus is a different deck band). NEVER a "
                 "branch input; a REPLICATION reported beside Stage 1, not a "
                 "re-adjudication of it.",
    }

    planned_n = (args.planned_n if args.planned_n is not None
                 else plan_bundle["plan"].get("n_positions"))

    return {
        "schema": SCHEMA, "design_doc": DESIGN_DOC, "read_rule": READ_RULE,
        "generated_utc": AT._now_utc(),
        "judges": {
            "IF": "clair-puct (production curve125 leaf, leaf hash a36d2e15a3b3d71d, "
                  "PUCT @ 100 clairvoyant sims, played to terminal on a known deck)",
            "ARB": "tier1-greedy (RuleBasedPlayer, v1 OBJECT leaf virtual_score_inplace, "
                   "1-ply argmax, no search, python-only, played to terminal)"},
        "args": {"if_records": str(if_root), "arb_records": arb_roots,
                 "plan_dir": args.plan_dir, "full_supply_plan": args.full_supply_plan,
                 "split": args.split, "pilot": args.pilot, "out_dir": args.out_dir,
                 "boot_seed": args.boot_seed, "rnd_seed": args.rnd_seed,
                 "parity_base": args.parity_base, "sigma_game": args.sigma_game,
                 "bootstrap_reps": BOOT_REPS, "rho_source": args.rho_source,
                 "n_floor_pooled": args.n_floor_pooled,
                 "n_floor_slice": args.n_floor_slice},
        "constants": {"ratio_bar": RATIO_BAR, "z_bar": Z_BAR,
                      "fixed_denominator": FIXED_DENOM,
                      "fixed_denominator_se": FIXED_DENOM_SE,
                      "g_boot_bar": GBOOT_BAR, "drift_bar": DRIFT_BAR,
                      "rho_bar": RHO_BAR, "m_expected": M_EXPECTED,
                      "b_ladder": list(B_LADDER), "b_honest": B_HONEST,
                      "n_floor_pooled": args.n_floor_pooled,
                      "n_floor_slice": args.n_floor_slice,
                      "fullset_extrapolation": AT.FULLSET_EXTRAP,
                      "tied_tile_plies_per_game": AT.TIED_TILE_PLIES_PER_GAME,
                      "champ_moves_per_game": CHAMP_MOVES_PER_GAME,
                      "non_additivity": AT.NON_ADDITIVITY,
                      "non_additivity_low_end": AT.NON_ADDITIVITY_LOW_END,
                      "sigma_game_walled": AT.SIGMA_GAME_WALLED,
                      "sigma_game_fixed_v1": AT.SIGMA_GAME_FIXED_V1},
        "completion": {
            "planned_positions": counts["planned"],
            "planned_n": planned_n, "target_n": args.target_n,
            "completion_frac": (len(rows) / planned_n) if planned_n else None,
            "n_analysed": len(rows), "n_roots": len(analysed_roots),
            "n_S1": len(slices_rows["S1"]), "n_S2": len(slices_rows["S2"]),
            "n_unsplit": counts["unsplit"], "unsplit_roots": counts["unsplit_roots"],
            "m_realized": m_realized,
            "m_matches_design": bool(set(m_realized) == {M_EXPECTED}),
            "world_seed_salt_realized": sorted(
                set(cross["world_seed_salt_if"]) | set(cross["world_seed_salt_arb"])),
            "world_seed_salt_agrees_across_judges": bool(
                cross["world_seed_salt_if"] == cross["world_seed_salt_arb"]),
            "world_seed_salt_note": (
                "READ off the records (`world_seed_salt`), never assumed. DESIGN §0.A "
                "withdrew §4.5's `tiearb2-v1`: run_tiletie's WORLD_SEED_SALT is a module "
                "constant and world freshness is carried by the root-disjoint `rid`s, not "
                "by the salt. G-CRN independently proves the two judges' seeds are "
                "bit-identical."),
            "excluded": {k: counts[k] for k in ("absent_if", "absent_arb",
                                                "armset_mismatch", "partial",
                                                "champ_arm_absent")},
            "armset_mismatch_frac": counts["armset_mismatch_frac"],
            "armset_frac_note": counts["armset_frac_note"],
            "armset_mismatch_rids": counts["armset_mismatch_rids"],
            "champ_absent_rids": counts["champ_absent_rids"],
            "records_not_ok": {"if": len(if_not_ok), "arb": len(arb_not_ok)},
            "records_present": {"if": if_present, "arb": arb_present},
            "composition": composition(rows),
        },
        "split": {"file": args.split, "seed": split_doc.get("seed"),
                  "balance_ok": split_doc.get("balance_ok"),
                  "n_cells": len(split_doc.get("cells") or {}),
                  "cells": split_doc.get("cells"),
                  "n_S1_roots_in_split": split_doc.get("n_S1_roots"),
                  "n_S2_roots_in_split": split_doc.get("n_S2_roots"),
                  "n_S1_roots_analysed": len(s1r), "n_S2_roots_analysed": len(s2r),
                  "analysed_roots_covered": bool(analysed_roots <= split_roots)},
        "integrity": {"per_judge": integ, "cross_judge_G_CRN": cross},
        "preconditions": pre,
        "statistics": blocks,
        "primary": primary,
        "b_ladder": ladders,
        "cost": cost,
        "companions": {
            "C-RND": {sl: (blocks[sl]["rnd_all"] if blocks[sl] else None)
                      for sl in ("pooled", "S1", "S2")},
            "arb_minus_rnd": {x: {sl: (blocks[sl][f"arb_{x}_minus_rnd_all"]
                                       if blocks[sl] else None)
                                  for sl in ("pooled", "S1", "S2")} for x in ARMS},
            "C-ARM0": {x: P[f"arm0_{x}_all"] for x in ARMS},
            "SEC-ARB": {x: dict(P[f"sec_{x}_all"], label=(
                "⚠️ AUDIT-ONLY, CIRCULAR: the arbiter's picks priced by tier1-greedy "
                "ITSELF. Its capture fraction against its own headroom is 1 BY "
                "CONSTRUCTION. NEVER a branch input.")) for x in ARMS},
            "PICKCHG": pickchg,
            "AGREE_HC": {
                "frac_same_arm_both_folds": AT._mean(
                    [1.0 if r["agree_hc"] else 0.0 for r in rows]),
                "B_honest": B_HONEST, "B_cheap": b_star,
                "note": "the cheapest possible readout of how much the world budget "
                        "matters. 1.0 by construction when B* == 16."},
            "arb_H_minus_arb_C": arm_diff,
            "coverage": 1.0,
            "coverage_note": "1.0 BY CONSTRUCTION — the arbiter selects only from the "
                             "scored arm set. Reported as a witness, not a conjunct.",
        },
        "sign_check": sign,
        "bounds": {"arb_H": bound(P["arb_H_all"], "pooled/arb_H"),
                   "arb_C": bound(P["arb_C_all"], "pooled/arb_C"),
                   "ora": bound(P["ora_all"], "pooled/ora"),
                   "note": "×1.40 full-set extrapolation and the ÷3.2 chain applied "
                           "IDENTICALLY to numerator and denominator, so they CANCEL OUT "
                           "OF F. Every caveat inherited verbatim: NON_ADDITIVITY=3.2 is "
                           "n=1 with a ÷5.23 low-end bracket — a ±1.6× bracket, not a "
                           "point. The linear-φ step degrades above ~1σ."},
        "resolution": {
            "sd_positions_arb_H": P["arb_H_all"]["sd_positions"],
            "two_sigma_pts": two_sigma,
            "two_sigma_elo": (AT.pts_to_elo(two_sigma * AT.FULLSET_EXTRAP,
                                            sigma_game=args.sigma_game)
                              if two_sigma == two_sigma else None),
            "two_sigma_in_F_fixed_units": (two_sigma / FIXED_DENOM
                                           if two_sigma == two_sigma else None),
            "n_for_F_fixed_pm_0.35": n_for_pm,
            "note": "DESIGN §6 sized the corpus so the POOLED read resolves the bar it is "
                    "graded at (2σ = 0.302 in F_fixed units at n = 1,400 vs a 0.35 bar). "
                    "n scales the realized CLUSTER-ROBUST se (design effect included).",
        },
        "cuts_never_adjudicated": cut_blocks(rows),
        "stage1_comparison": stage1_cmp,
        "adjudication": adj,
        "governance": (
            "Measurement only. 0 strength games on EVERY branch. The 850 self-play games "
            "are corpus SUBSTRATE. No experiments/results.csv row, no band, no "
            "governance/BAND_REGISTRY.csv entry, no claim id minted, "
            "governance/PRODUCTION.yaml untouched. This read-rule is SPENT when this "
            "read-out lands."),
        "_rows": rows,
    }


# --------------------------------------------------------------------------- #
# RENDERING — READ_RULE §4.2's mandatory list 1..13, in that order              #
# --------------------------------------------------------------------------- #
_f = TA._f
_row = TA._row


def _arm_label(x, b):
    return f"`{x}` ({'honest' if x == 'H' else 'cheap'}, B = {b})"


def render(v: dict) -> str:
    L = []
    A = L.append
    adj = v["adjudication"]
    c = v["completion"]
    cost = v["cost"]
    P = v["primary"]["pooled"]

    A("# TERMINAL-GROUNDED TIE ARBITRATION — READ-OUT (Stage 1b, offline)")
    A("")
    A(f"**Branch: `{adj['branch']}` — {adj['branch_headline']}** — adjudicated mechanically "
      f"by [READ_RULE.md](READ_RULE.md), committed before any number existed.")
    A("")
    A(adj["read"])
    A("")
    if adj["branch"] == "U-UNREADABLE":
        A(f"**Failed precondition(s):** {', '.join(adj['failed_preconditions'])}.")
        A("")
    else:
        for x in ARMS:
            fc = adj["failed_conjuncts"].get(x) or []
            if fc:
                A(f"**Conjunct(s) that failed for arm {_arm_label(x, cost['B_star'] if x == 'C' else 16)}:** "
                  f"{'; '.join(fc)}.")
        A("")
    if adj["branch"] == "F-FLAT2":
        A(f"> ⚠️ **MANDATORY SCOPE SENTENCE, never separated from the verdict:** "
          f"*\"{adj['mandatory_scope_sentence']}\"*")
        A("")
        if adj.get("rider_35pct_capture_excluded"):
            A("> **Rider (applies):** `F_fixed_hi(H)` < 0.35, so a **35% capture IS "
              "excluded at 95%** and the scope sentence above is superseded in that one "
              "respect.")
            A("")
        s1 = v["stage1_comparison"]
        A(f"> ⚠️ **Second rider, mandatory always on this branch:** Stage 1 read "
          f"`F_fixed = {STAGE1['F_fixed']}` (`arb = +{STAGE1['arb']}`, z "
          f"{STAGE1['z_arb']}) on the spent corpus, so this is a **DIRECT CONTRADICTION "
          f"OF A PUBLISHED RESULT**. Here: `arb_H` = {_f(s1['here_arb_H'])}, "
          f"`F_fixed` = {_f(s1['here_F_fixed_H'], 3)}; difference "
          f"{_f(s1['difference_arb'])} ± {_f(s1['se_of_difference'])} "
          f"(z {_f(s1['z_of_difference'], 2)}). **The contradiction is NOT presented as "
          f"resolved.**")
        A("")
        A(f"**Operative statement of the tile-tie axis, recorded on this branch:** "
          f"*{adj['operative_axis_statement']}*")
        A("")
    if adj["branch"] in ("A-DEPLOYABLE", "A-COSTLY"):
        for x in ARMS:
            if v["sign_check"][x]["corroboration"].startswith("NO"):
                A(f"> ⚠️ The §5.6 sign check on arm `{x}` reads **NO CORROBORATION**. "
                  f"READ_RULE §4 requires the licensed Stage-2 prereg to carry that "
                  f"verdict **verbatim**.")
        A("")
    A(f"- IF judge: {v['judges']['IF']}")
    A(f"- ARB judge: {v['judges']['ARB']}")
    A(f"- arms: **`H` honest B = {B_HONEST}** · **`C` cheap B = {cost['B_star']}** "
      f"({cost['B_star_source']})")
    A(f"- n = **{c['n_analysed']}** positions / {c['n_roots']} roots "
      f"(S1 {c['n_S1']} · S2 {c['n_S2']}"
      + (f" — {100.0*c['completion_frac']:.1f}% of the planned {c['planned_n']}"
         if c.get("completion_frac") else "")
      + f"); M = {c['m_realized']} CRN worlds, realized salt "
        f"`{'/'.join(c['world_seed_salt_realized']) or 'not recorded'}` "
        f"(read off the records, not assumed — DESIGN §0.A), "
        f"**seeds bit-identical between the two judges**")
    if not c["m_matches_design"]:
        A("")
        A(f"> ⚠️ **`M` DOES NOT MATCH THE DESIGN.** DESIGN §4.5 locks `M = "
          f"{M_EXPECTED}` and states it is load-bearing (the cross-fit selects on M/2 and "
          f"evaluates on M/2, so a larger M makes the estimand LARGER). Realized: "
          f"{c['m_realized']}.")
    A("")
    A("> ⚠️ **The branch input is the POOLED read** (READ_RULE §1). Unlike Stage 1 this is "
      "not a deviation: DESIGN §6 sizes the corpus so the pooled read resolves the bar it "
      "is graded at. The stratified half-split enters as the consistency conjunct "
      "`C_split`, with the informativeness guard and the baseline-drift gate input.")
    A("")
    A("> ⚠️ **This read-rule is SPENT when this read-out lands**, on every branch.")
    A("")

    # ---- 1 ---------------------------------------------------------------- #
    A("## 1. The primary statistics — both arms, pooled / S1 / S2, both scalings")
    A("")
    for sl in ("pooled", "S1", "S2"):
        pr = v["primary"].get(sl)
        if not pr:
            A(f"### {sl} — **EMPTY**")
            A("")
            continue
        A(f"### {sl}  (n = {pr['n']} positions, {pr['n_roots']} roots, "
          f"{_f(pr['positions_per_root'], 2)} positions/root)")
        A("")
        A(f"- **`ora` = {_f(pr['ora'])}** (se {_f(pr['se_ora'])}, **z "
          f"{_f(pr['z_ora'], 2)}**), boot CI [{_f(pr['ora_boot_lo'])}, "
          f"{_f(pr['ora_boot_hi'])}] — the headroom, ONE `ora` for both arms")
        A(f"- **`rnd` = {_f(pr['rnd'])}** (se {_f(pr['se_rnd'])}, z "
          f"{_f(pr['z_rnd'], 2)}) — the null level")
        for x in ARMS:
            a = pr["arms"][x]
            A(f"- **arm {_arm_label(x, a['B'])}: `arb` = {_f(a['arb'])}** "
              f"(se {_f(a['se'])}, **z {_f(a['z'], 2)}**), boot CI "
              f"[{_f(a['boot_lo'])}, {_f(a['boot_hi'])}] · "
              f"**`F` = {_f(a['F'], 3)}** CI [{_f(a['F_lo'], 3)}, {_f(a['F_hi'], 3)}] · "
              f"**`F_fixed` = {_f(a['F_fixed'], 3)}** CI [{_f(a['F_fixed_lo'], 3)}, "
              f"{_f(a['F_fixed_hi'], 3)}] · `G-BOOT` {_f(a['G-BOOT'], 4)} ⇒ "
              f"**{'FIRED — F is VOID as a branch input; the ratio conjunct rests on F_fixed alone' if a['G-BOOT_fired'] else 'not fired'}** · "
              f"`arb − rnd` = {_f(a['arb_minus_rnd'])}")
        A("")
        blk = v["statistics"][sl]
        A("| statistic | n | mean | se (cluster) | 95% CI (boot) | z |")
        A("|---|---|---|---|---|---|")
        for name, _k in STAT_KEYS:
            A(_row(f"`{name}` — all (`scale_all`)", blk[f"{name}_all"]))
            A(_row(f"`{name}` — discriminable", blk[f"{name}_discriminable"]))
        A("")
    A(f"- bars: ratio **{RATIO_BAR}**, z **+{Z_BAR}**, cost **{RHO_BAR}** — the first two "
      f"are *not new constants* (E-FLAT's and W-FLAT's own committed fund bar, verbatim, "
      f"and Stage 1's); the third is the house N4 trigger currency.")
    A(f"- ⚠️ `F_fixed`'s denominator **{FIXED_DENOM} ± {FIXED_DENOM_SE}** was measured on "
      f"the SPENT corpus's dev slice, so `F_fixed` is now a **cross-corpus** ratio "
      f"(DESIGN §5.3). `F` is the internally-consistent statistic and `RBAR` requires "
      f"**both**.")
    A("")

    # ---- 2 ---------------------------------------------------------------- #
    A("## 2. The single-fold `parity_base=1` readings (the `I1` diagnostic)")
    A("")
    A("| slice | `arb_H` sym | `arb_H` p-base1 | `arb_C` sym | `arb_C` p-base1 | "
      "`ora` sym | `ora` p-base1 |")
    A("|---|---|---|---|---|---|---|")
    for sl in ("pooled", "S1", "S2"):
        blk = v["statistics"].get(sl)
        if not blk:
            continue
        A(f"| {sl} | {_f(blk['arb_H_all']['mean'])} | "
          f"{_f(blk['arb_H_parity_base1_all']['mean'])} | "
          f"{_f(blk['arb_C_all']['mean'])} | "
          f"{_f(blk['arb_C_parity_base1_all']['mean'])} | "
          f"{_f(blk['ora_all']['mean'])} | {_f(blk['ora_parity_base1_all']['mean'])} |")
    A("")
    A("Both headline statistics are **symmetrized over the two parity folds**, so the "
      "pricing run's `I1` parity-base ambiguity cannot be a lever.")
    A("")

    # ---- 3 ---------------------------------------------------------------- #
    A("## 3. `C-RND` per slice, the informativeness guard, and the escape clause")
    A("")
    A("| slice | `rnd` | se | z | `z(ora_s)` | INFORMATIVE? | `arb_H` | `arb_H − rnd` | "
      "`arb_C` | `arb_C − rnd` |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for sl in ("pooled", "S1", "S2"):
        pr = v["primary"].get(sl)
        blk = v["statistics"].get(sl)
        if not pr or not blk:
            continue
        info = ("—" if sl == "pooled"
                else ("**INFORMATIVE**" if sl in adj.get("informative_slices", [])
                      else "UNINFORMATIVE"))
        rr = blk["rnd_all"]
        A(f"| {sl} | {_f(rr['mean'])} | {_f(rr['se_cluster'])} | {_f(rr['z'], 2)} | "
          f"{_f(pr['z_ora'], 2)} | {info} | {_f(pr['arms']['H']['arb'])} | "
          f"{_f(pr['arms']['H']['arb_minus_rnd'])} | {_f(pr['arms']['C']['arb'])} | "
          f"{_f(pr['arms']['C']['arb_minus_rnd'])} |")
    A("")
    A(f"- `D_rnd = |rnd_S1 − rnd_S2|` = **{_f(adj.get('D_rnd'))}** vs the bar "
      f"{DRIFT_BAR} ⇒ `BASELINE_DRIFTED` = "
      f"**{adj.get('baseline_drifted')}**")
    A(f"- INFORMATIVE slices (`z(ora_s) ≥ +{Z_BAR}`): "
      f"**{adj.get('informative_slices') or 'NONE'}**. ⚠️ A slice that is not "
      f"INFORMATIVE reads **UNINFORMATIVE, never FAIL** — but `C_split` requires at "
      f"least one INFORMATIVE slice, so the guard is **not free**.")
    esc = adj.get("escape_clause_used") or {}
    used = [f"arm {x}/{s}" for x, d in esc.items() for s, u in (d or {}).items() if u]
    A(f"- **Escape clause (`BASELINE_DRIFTED ∧ (arb_s − rnd_s) ≥ 0`) used:** "
      f"**{', '.join(used) if used else 'NO — not used for any slice or arm'}**")
    A("")
    A("**DESIGN §12.3, mandatory when it applies:** `arb` under an *uninformative* arbiter "
      "is `mean-over-arms − champ`, not 0. If `C-RND` is materially positive, part of "
      "`arb` is not the mechanism — hence `arb − rnd` is printed beside `arb` everywhere. "
      "It is a gate input for the *consistency* conjunct ONLY; the primary estimand "
      "remains `arb`.")
    A("")

    # ---- 4 ---------------------------------------------------------------- #
    A("## 4. `C-ARM0` and `SEC-ARB`")
    A("")
    comp = v["companions"]
    A("| companion | n | mean | se | 95% CI | z |")
    A("|---|---|---|---|---|---|")
    for x in ARMS:
        A(_row(f"`C-ARM0` arm {x} — arm-0 comparator (`headroom_leaf` currency)",
               comp["C-ARM0"][x]))
    for x in ARMS:
        A(_row(f"`SEC-ARB` arm {x} ⚠️ AUDIT-ONLY, CIRCULAR", comp["SEC-ARB"][x]))
    A("")
    A("⚠️ **`SEC-ARB` is CIRCULAR by construction**: it is the arbiter's picks priced by "
      "`tier1-greedy` *itself*, i.e. the ARB judge's own cross-fit headroom, so its "
      "**capture fraction against its own headroom is 1 BY CONSTRUCTION**. It is reported "
      "in pts with its `z` and is **never a branch input**.")
    A("")

    # ---- 5 ---------------------------------------------------------------- #
    A("## 5. The full B-ladder — capture × cost")
    A("")
    A("⚠️ **A REPORTED LADDER, NEVER A BRANCH INPUT except at `B = 16` (arm `H`) and "
      f"`B = {cost['B_star']}` (arm `C`)**, both named in advance. Every rung is a "
      "**sub-read of records this run already paid for** (the world seeds are "
      "prefix-stable in `M`), so the cost answer costs 0 extra worker-seconds.")
    A("")
    A("| B | `arb` | se | z | `F` | `F_fixed` | `rho_wall` | `rho_amortized` | "
      "`rho_phone` | ≤ 1.20? | role |")
    A("|---|---|---|---|---|---|---|---|---|---|---|")
    lad = v["b_ladder"]["pooled"]
    rl = cost["ladder_from_pilot_c"] if cost["c_tier1_branch_source"] == "pilot" \
        else cost["ladder_from_realized_c"]
    for b in B_LADDER:
        d = lad[str(b)]
        r = rl.get(str(b), {})
        role = []
        if b == B_HONEST:
            role.append("**arm `H`**")
        if b == cost["B_star"]:
            role.append("**arm `C` (B\\*)**")
        A(f"| {b} | {_f(d['arb'])} | {_f(d['se'])} | {_f(d['z'], 2)} | "
          f"{_f(d['F'], 3)} | {_f(d['F_fixed'], 3)} | {_f(r.get('rho_wall'), 3)} | "
          f"{_f(r.get('rho_amortized'), 3)} | {_f(r.get('rho_phone'), 1)} | "
          f"{'✅' if r.get('legal') else '❌'} | {' · '.join(role) or '—'} |")
    A("")
    A(f"- **`B*` = {cost['B_star']}** — {cost['B_star_source']}; re-derived from the "
      f"DESIGN §7.2 cost rule here: **{cost['B_star_rederived_from_cost_rule']}** "
      f"({'MATCHES' if cost['B_star_matches_cost_rule'] else '⚠️ DOES NOT MATCH'})")
    A(f"- **`Ā` = {_f(cost['A_bar_mean_arms'], 4)}** ({cost['A_bar_source']}) · "
      f"**`c_tier1` (pilot) = {_f(cost['c_tier1_pilot'], 4)}** worker-s/playout · "
      f"`c_tier1` (realized from records) = "
      f"{_f(cost['c_tier1_realized_from_records'], 4)}")
    A(f"- **`rho_wall(B*)` = {_f(cost['rho_wall_bstar'], 3)}** vs the bar "
      f"{RHO_BAR} ⇒ **`DEPLOY` = {adj.get('DEPLOY')}** "
      f"(c source: `{cost['c_tier1_branch_source']}`)")
    A(f"- `rho_wall(B) = Ā × B × c_tier1 / {T_CHAMP}` · "
      f"`rho_amortized = rho_wall × {AT.TIED_TILE_PLIES_PER_GAME}/{CHAMP_MOVES_PER_GAME:.0f}` · "
      f"`rho_phone = Ā × B × c_tier1 / {T_PHONE}`")
    A(f"- {cost['note']}")
    A("")

    # ---- 6 ---------------------------------------------------------------- #
    A("## 6. `PICKCHG`, coverage and `AGREE_HC`")
    A("")
    A("| arm | `a_arb ≠ champ` (either fold) | fold 1 | fold 2 | `a_arb = a_ora` |")
    A("|---|---|---|---|---|")
    for x in ARMS:
        p = comp["PICKCHG"][x]
        A(f"| {x} | {_f(p['frac_pick_changed'], 3)} | "
          f"{_f(p['frac_pick_changed_fold1'], 3)} | "
          f"{_f(p['frac_pick_changed_fold2'], 3)} | "
          f"{_f(p['frac_selector_agreement'], 3)} |")
    A("")
    ah = comp["AGREE_HC"]
    A(f"- **`AGREE_HC` = {_f(ah['frac_same_arm_both_folds'], 3)}** — the fraction where "
      f"the cheap arm (B = {ah['B_cheap']}) and the honest arm (B = {ah['B_honest']}) "
      f"select the **same** arm in **both** folds. {ah['note']}")
    ad = comp["arb_H_minus_arb_C"]
    A(f"- **`arb_H − arb_C` = {_f(ad['mean'])}** ± {_f(ad['se_cluster_paired'])} "
      f"(paired cluster-robust, z {_f(ad['z'], 2)}) — {ad['note']}")
    A(f"- coverage = **{comp['coverage']:.1f}** — {comp['coverage_note']}")
    A("")

    # ---- 7 ---------------------------------------------------------------- #
    A("## 7. The §5.6 sign check (E4 autopsy taxonomy, unchanged)")
    A("")
    for x in ARMS:
        s = v["sign_check"][x]
        A(f"**arm `{x}`** — over the **{s['n_pickchg']}** positions where the arbiter "
          f"changes the champion's pick in at least one fold: "
          f"{s['n_agree']}/{s['n_nonzero']} = **{_f(s['agreement_rate'], 3)}** with "
          f"`arb[p] > 0`, exact two-sided binomial **p "
          f"{s['binomial_p_two_sided']:.3g}**; aggregate sign "
          f"**{s['aggregate_sign']:+d}**, per-position majority "
          f"{s['per_position_majority_sign']:+d}, mean over the pick-change positions "
          f"{_f(s['mean_over_pickchg_positions'])} ⇒ **{s['corroboration']}**")
        A("")
    A(f"- benchmarks: {BENCH}")
    A("- ⚠️ **MANDATORY on every branch; NEVER a branch input** (the OOF precedent: 57.1% "
      "at p 0.0547 = NO CORROBORATION while the mean convicted at z +4.32).")
    A("")

    # ---- 8 ---------------------------------------------------------------- #
    A("## 8. The bound chain — pts and elo, with the ±1.6× bracket")
    A("")
    A("| term | pts/tied tile ply (×1.40 full-set) | 95% CI | elo (÷3.2) | elo 95% CI | "
      "elo (÷5.23 low-end) |")
    A("|---|---|---|---|---|---|")
    for nm in ("arb_H", "arb_C", "ora"):
        b = v["bounds"].get(nm)
        if not b:
            continue
        A(f"| `{nm}` | {_f(b['pts_per_tied_tile_ply']['point'])} | "
          f"[{_f(b['pts_per_tied_tile_ply']['ci95_lo'])}, "
          f"{_f(b['pts_per_tied_tile_ply']['ci95_hi'])}] | "
          f"{_f(b['elo']['point'], 2)} | [{_f(b['elo']['ci95_lo'], 2)}, "
          f"{_f(b['elo']['ci95_hi'], 2)}] | "
          f"{_f(b['elo_low_end_divisor_5.23']['point'], 2)} |")
    A("")
    ba = v["bounds"].get("arb_H")
    if ba:
        A("**σ_game sensitivity** on `arb_H`'s CI-hi: "
          + " · ".join(f"σ={k} → {_f(x, 2)} elo"
                       for k, x in ba["elo_sigma_sensitivity"].items())
          + ". elo scales as 1/σ_game, so the SMALLER σ is the larger, "
            "conservative-against-closure bound.")
        A("")
    A(f"⚠️ {v['bounds']['note']}")
    A("")

    # ---- 9 ---------------------------------------------------------------- #
    A("## 9. Realized `n`, roots, positions-per-root and composition per slice")
    A("")
    A(f"- planned positions in the corpus: **{c['planned_positions']}** "
      f"(plan `n_positions` {c['planned_n']}, DESIGN target {c['target_n']}) · analysed: "
      f"**{c['n_analysed']}** over {c['n_roots']} roots"
      + (f" = **{100.0*c['completion_frac']:.1f}%** of plan" if c.get("completion_frac")
         else ""))
    A(f"- slices: **S1 {c['n_S1']}** · **S2 {c['n_S2']}** · unsplit (a `G-SPLIT` "
      f"failure if non-zero): **{c['n_unsplit']}**")
    A(f"- excluded and counted: {c['excluded']} "
      f"(`G-ARMSET` mismatch fraction {_f(c['armset_mismatch_frac'], 4)}; "
      f"{c['armset_frac_note']})")
    A("")
    A("| slice | n | roots | pos/root | phase | arm-count | capped | profile |")
    A("|---|---|---|---|---|---|---|---|")
    for sl, d in c["composition"].items():
        A(f"| {sl} | {d['n']} | {d['n_roots']} | {_f(d['positions_per_root'], 2)} | "
          f"{d['by_phase']} | {d['by_arm_count']} | {d['capped']} | {d['by_profile']} |")
    A("")
    sp = v["split"]
    A(f"**The 18-cell balance witness** (`SPLIT.json`, seed {sp['seed']}, "
      f"`balance_ok` = **{sp['balance_ok']}**, {sp['n_cells']} cells):")
    A("")
    A("| cell (`phase|arms|champ_is_arm0`) | roots | S1 roots | S2 roots | S1 pos | "
      "S2 pos | balanced |")
    A("|---|---|---|---|---|---|---|")
    for cell, d in (sp["cells"] or {}).items():
        A(f"| `{cell}` | {d['n_roots']} | {d['n_S1_roots']} | {d['n_S2_roots']} | "
          f"{d['n_S1_positions']} | {d['n_S2_positions']} | "
          f"{'ok' if d.get('balanced') else '**OFF**'} |")
    A("")

    # ---- 10 --------------------------------------------------------------- #
    A("## 10. Every §3 gate and every DESIGN §9 integrity counter")
    A("")
    A("| precondition | result |")
    A("|---|---|")
    for k, ok in v["preconditions"].items():
        A(f"| `{k}` | {'PASS' if ok else '**FAIL**'} |")
    A("")
    A("**Per-judge `analyze_tiletie` §2.1 witnesses:**")
    A("")
    for j, blk in v["integrity"]["per_judge"].items():
        A(f"- `{j}`: " + " · ".join(f"{k} {val}" for k, val in sorted(blk.items())))
    A("")
    cr = v["integrity"]["cross_judge_G_CRN"]
    A("**Cross-judge CRN witness (`G-CRN`)** — the ARB record's `world_seeds` / "
      "`playout_seeds` must be **bit-identical** to the `clair-puct` record for the same "
      "rid+leg, and `pick_a`/`pick_b` must match:")
    A("")
    for k in ("compared_legs", "crn_cross_mismatch", "seed_cross_mismatch",
              "arm_cross_mismatch"):
        A(f"- `{k}`: **{cr[k]}**")
    if cr["examples"]:
        A(f"- ⚠️ examples: {cr['examples']}")
    A(f"- realized `world_seed_salt`: IF {cr['world_seed_salt_if'] or 'not recorded'} · "
      f"ARB {cr['world_seed_salt_arb'] or 'not recorded'} — agree across judges: "
      f"**{c['world_seed_salt_agrees_across_judges']}**. {c['world_seed_salt_note']}")
    A("")
    A(f"- `G-SPLIT`: analysed roots covered by SPLIT.json = "
      f"**{sp['analysed_roots_covered']}** · S1 {sp['n_S1_roots_analysed']} roots / S2 "
      f"{sp['n_S2_roots_analysed']} roots analysed (of {sp['n_S1_roots_in_split']} / "
      f"{sp['n_S2_roots_in_split']} carved) · cells {sp['n_cells']} · `balance_ok` "
      f"{sp['balance_ok']}")
    pil = cost["pilot"]
    A(f"- `G-REPRO` (the pilot's bit-reproduction of the spent-corpus records, a "
      f"PRE-LAUNCH abort): **{pil.get('g_repro') if pil.get('g_repro') is not None else 'not recorded in PILOT.json'}**")
    A("- `G-DISJOINT` (three intersections, root / rid / position digest), `G-LEAF` "
      "(harness leaf hash `a36d2e15a3b3d71d`), `G-REPRO` and `G-GEN` are **pre-launch "
      "aborts** witnessed by `DISJOINTNESS.json` / `GATE_BACKEND_RECHECK_*.json` / the "
      "generation log, not by this analyser.")
    A("")

    # ---- 11 --------------------------------------------------------------- #
    A("## 11. Realized `c_tier1`, resolution, sizing and the process census")
    A("")
    r = v["resolution"]
    cfm = cost["c_tier1_from_run_manifests"]
    A(f"- realized `c_tier1` from the ARB records' own `elapsed_secs`: "
      f"**{_f(cost['c_tier1_realized_from_records'], 4)}** worker-s/playout — "
      f"**the preferred source**")
    A(f"- from `RUN_MANIFEST*.json` ({cfm['n_legs']} legs, key spellings seen "
      f"{cfm['key_spelling_seen'] or 'none'}, playouts from "
      f"`{cfm['playouts_source']}`): Σ`elapsed_secs` ⇒ "
      f"{_f(cfm['c_from_elapsed_secs'], 4)} · Σ(`wall_secs`×`workers`) ⇒ "
      f"{_f(cfm['c_from_wall_times_workers'], 4)} (a wall-clock UPPER bound)")
    A(f"- ⚠️ {cfm['note']}")
    A(f"- pilot `c_tier1` (the one that froze `B*`): "
      f"**{_f(cost['c_tier1_pilot'], 4)}**")
    A(f"- realized per-position sd of `arb_H` = {_f(r['sd_positions_arb_H'])} pts")
    A(f"- realized **2σ resolution = {_f(r['two_sigma_pts'])} pts** = "
      f"{_f(r['two_sigma_elo'], 2)} elo = **{_f(r['two_sigma_in_F_fixed_units'], 3)}** in "
      f"`F_fixed` units (DESIGN §6 projected 0.302 at n = 1,400)")
    A(f"- `n` that would resolve `F_fixed` to ±0.35 at the realized dispersion: "
      f"**≈ {('%.0f' % r['n_for_F_fixed_pm_0.35']) if r.get('n_for_F_fixed_pm_0.35') else 'n/a'}** "
      f"positions")
    A(f"- co-tenant found by the process census: "
      f"**{pil.get('co_tenant') or 'none recorded'}** — DESIGN §12.10: no value depends "
      f"on wall-clock except `c_tier1`, which sets `B*`.")
    A("")

    # ---- 12 --------------------------------------------------------------- #
    A("## 12. Cuts — emitted beside the pooled read, ⚠️ UNDERPOWERED, NEVER adjudicated on")
    A("")
    A("| cut | n | roots | `arb_H` | z | `ora` | z | `F` | `F_fixed` |")
    A("|---|---|---|---|---|---|---|---|---|")
    for nm, d in v["cuts_never_adjudicated"].items():
        A(f"| {nm} | {d['n']} | {d['n_roots']} | {_f(d['arb'])} | {_f(d['z_arb'], 2)} | "
          f"{_f(d['ora'])} | {_f(d['z_ora'], 2)} | {_f(d['F_point'], 3)} | "
          f"{_f(d['F_fixed_point'], 3)} |")
    A("")
    A("Per-phase / per-arm-count / capped reads are **underpowered on their own and are "
      "labelled as such**; **no branch is ever adjudicated on a cut** (DESIGN §5.5). "
      "⚠️ This corpus is a SINGLE stratum / profile / rules epoch (DESIGN §4.2), so the "
      "per-stratum and per-profile cuts are degenerate by construction.")
    A("")

    # ---- 13 --------------------------------------------------------------- #
    A("## 13. Direct comparison to Stage 1 — ⚠️ a CROSS-CORPUS contrast")
    A("")
    s1 = v["stage1_comparison"]
    A("| statistic | Stage 1 (spent, n = 733) | here (fresh) | difference | se(diff) | z |")
    A("|---|---|---|---|---|---|")
    A(f"| `arb` (honest arm) | {_f(STAGE1['arb'])} | {_f(s1['here_arb_H'])} | "
      f"{_f(s1['difference_arb'])} | {_f(s1['se_of_difference'])} | "
      f"{_f(s1['z_of_difference'], 2)} |")
    A(f"| `F_fixed` | {_f(STAGE1['F_fixed'], 3)} | {_f(s1['here_F_fixed_H'], 3)} | "
      f"{_f(s1['difference_F_fixed'], 3)} | — | — |")
    A("")
    A(f"- Stage 1's branch was **`{STAGE1['branch']}`** ({STAGE1['source']}).")
    A(f"- {s1['label']}")
    A("")

    # ---- governance ------------------------------------------------------- #
    A("## Governance")
    A("")
    A(v["governance"])
    A("")
    A("**DESIGN §12.1, which travels with every number above:** the arbiter and the "
      "pricing judge are *both terminal-grounded*. A positive here is evidence that "
      "terminal grounding at ties is worth points **as measured by a terminal-grounded "
      "ruler** — it is **NOT yet evidence of deploy elo**. DESIGN §12.2: positions were "
      "selected on a *leaf* property, so regression to the mean cuts **toward the null** "
      "— a positive read is conservative.")
    return "\n".join(L) + "\n"


def main(argv=None) -> int:
    args = parse_args(argv)
    v = build_readout(args)
    rows = v.pop("_rows")
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "READOUT.json").write_text(json.dumps(v, indent=1, default=str))
    (out / "READOUT.md").write_text(render(v))
    (out / "per_position.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows))
    print(render(v))
    print(f"\n[wrote] {out/'READOUT.json'}\n[wrote] {out/'READOUT.md'}\n"
          f"[wrote] {out/'per_position.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
