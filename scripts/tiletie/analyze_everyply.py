#!/usr/bin/env python3
"""Adjudicate ``measurement/everyply_probe_20260823/READ_RULE.md`` — EVERY-PLY
ROLLOUT ARBITRATION, SIZE-1 kill-screen. **Mechanically. No owner call
adjudicates any outcome.**

Joins the two judges' CRN-paired records over the non-tied tile-ply corpus:

  * ``ARB`` = ``tier1-greedy`` (rust, B = 16) — the ARBITRATION policy, all K arms;
  * ``IF``  = ``clair-puct``   (rust, 100 clairvoyant sims) — the PRICING oracle,
    on the DESIGN §5.2 **selective** arm subset only,

and computes, per position, on the DESIGN §4.1 parity cross-fit (both folds,
symmetrized):

    a_arb   = argmax_a mean_{j in sel} V^ARB[p, a, j]          # ARBITRATION
    kappa[p]= mean_{j in eva} V^IF[p, a_arb, j]
            - mean_{j in eva} V^IF[p, champ,  j]               # PRICING
    kappa   = SUM_s w_s * mean_{p in s} kappa[p]   [pts per NON-TIED tile ply]
    z_kappa = kappa / se_cluster                   cluster-robust on root_id := game_id

then applies READ_RULE §3's eleven gates, §1's from-scratch witness, §4's branch
table in order (first match wins) subject to §0.A, and prints §4.3's numbers,
nine honesty rails and scope fence on EVERY branch.

IT COMPUTES NO ESTIMATOR THAT ALREADY EXISTS. ``parity_indices``,
``crossfit_regret``, ``cluster_robust``, ``bootstrap_roots``, ``aggregate``,
``load_plan``, ``discover_records``, ``pts_to_elo`` and the constants are
``analyze_tiletie``'s, **imported UNMODIFIED** — the same contract
``analyze_tiearb.py`` states in its own docstring. ``a_arb`` is literally
``crossfit_regret(matrix_arb, sel, eva, champ_pos)``'s own ``a_plus``, so the
argmax tie-break is shared by construction rather than re-typed, and it is the
SAME call ``build_everyply_corpus --mode selective`` made when it chose which
arms to price.

⚠️ ``probe_pickers.py`` CANNOT be run unmodified on this corpus — its ``grade`` /
``preflight`` / ``sweep`` subcommands call ``require_knowngood`` against constants
hard-pinned to the OLD 733/399 tiearb corpus and would fail-always here (DESIGN
§6.2). ``G-KNOWNGOOD`` therefore runs the ``knowngood`` SUBCOMMAND ONLY, as a
separate gate, FIRST, and this analyser refuses to read any other number if it
fails.

TWO ESTIMATOR ENTRY POINTS, DELIBERATELY SEPARATE (DESIGN §2.3):
``kappa_pooled`` population-reweights and therefore pays the stratification
price; ``kappa_stratum`` reweights nothing and must NOT. Collapsing them is how
the per-stratum figures silently gain 6%.

⛔ 0 games. No band, no claim id, no ``results.csv`` row, ``PRODUCTION.yaml``
untouched — on every branch (READ_RULE §0 / BAND_NOTE.md).
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import analyze_tiletie as AT                                       # noqa: E402
import build_everyply_corpus as EC                                 # noqa: E402
import build_everyply_plan as EP                                   # noqa: E402

SCHEMA = "carcassonne-everyply-readout/v1"
DESIGN_DOC = "measurement/everyply_probe_20260823/DESIGN.md"
READ_RULE_DOC = "measurement/everyply_probe_20260823/READ_RULE.md"
RUN_ID = "everyply_probe_20260823"

# ---- READ_RULE §1/§4 committed constants. NOTHING HERE MAY BE TUNED. ------- #
KAPPA_STAR = 0.15          # §4 branch 3 / DESIGN §4.4 — the fund bar
KAPPA_CLEAN = 0.35         # §4 branch 2 — the clean bar
KAPPA_HARM = -0.15         # §4 branch 1
Z_BAR = 2.0                # §4 — the conviction bar (== AT.Z_CONVICTION)
UB95_K = 2.0               # §1 — the DECLARED upper-bound convention (2.0, NOT 1.96)
SCALE_ALL = 1.0            # §1 / DESIGN §4.2 — there is no degenerate class here
PARITY_BASE = 1            # DESIGN §4.1 (analyze_tiletie I1)
M_EXPECTED = 32            # DESIGN §3.1 — load-bearing, must NOT be raised
N_PRICED_PLANNED = 400     # DESIGN §5.3 — the ONLY read point
G_N_FRACTION = 0.85        # §3 G-N — 0.85 * 400 = 340
G_DISTINCT_MAX = 0.10      # §3 G-DISTINCT
G_FRAME_MAX_PP = 3.0       # §3 G-FRAME
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"      # §3 G-EPOCH — the HARNESS dialect
RULES_PROFILE_OF_RECORD = "walled"            # §3 G-EPOCH / DESIGN §10 item 8
WITNESS_TOL = 1e-9         # §1 — "beyond floating-point tolerance" is U-UNREADABLE

# ---- DESIGN §4.3's elo chain. A BRACKET, never a point. -------------------- #
PLIES_PER_GAME = 12.812    # non-tied tile plies per game per seat (DESIGN §2.1)
NA_BRACKET = (0.31, 0.85)  # (÷3.2 prereg, Stage-2 realized)
ELO_PER_PTS_GAME = 7.79    # Stage-2 realized elo per pts/game
CELL_N = 800               # Stage-2's realized deck-paired cell size
CELL_RESOLVES_PTS = 1.38   # what an n=800 cell resolves at 2 sigma

STRATA = EP.STRATA         # ("A", "B", "C")

#: READ_RULE §3, in table order. Every one is a PRECONDITION; ANY fail is
#: U-UNREADABLE and NO branch may fire. FAIL-CLOSED: **ABSENT IS FAIL.**
GATE_IDS = ("G-KNOWNGOOD", "G-CRN", "G-COVER", "G-ARMSET", "G-ZEROFILL",
            "G-DISTINCT", "G-FRAME", "G-N", "G-EPOCH", "G-CHAMP", "G-BLIND")

BRANCH_ORDER = ("E-HARM", "E-CLEAN", "E-FUND", "E-FLATNULL", "E-UNRESOLVED")

#: READ_RULE §0.A — the positive branches are NOT REACHABLE at SIZE-1, by the
#: plan's own kill-only declaration. Named before game 1; NOT discovered after.
KILL_ONLY_BLOCKED = ("E-CLEAN", "E-FUND")

BRANCH_LICENCE = {
    "E-HARM": ("Every-ply arbitration is ACTIVELY HARMFUL at non-tied plies. Lever "
               "CLOSED; the LEVER_INDEX row \"every-ply rollout arbitration\" flips to "
               "KILLED. LICENSES NOTHING ELSE."),
    "E-CLEAN": ("Licenses A DESIGN FOR one deck-paired game cell (owner decision), "
                "resolvable at n = 800 under BOTH NA ends. NOT a game cell."),
    "E-FUND": ("Same, BUT the read-out must print n_cell at BOTH NA ends; under the "
               "conservative chain the cell it funds is NOT n=800."),
    "E-FLATNULL": ("A FUNDING VERDICT, NOT AN EXCLUSION — the same words W-FLAT and "
                   "F-FLAT used. Lever PARKED with its printed re-open bar."),
    "E-UNRESOLVED": ("NOTHING CLOSES, NOTHING IS LICENSED. The n that would resolve the "
                     "observed kappa_hat at the REALIZED dispersion is printed below; a "
                     "top-up decision would rest on it, and a top-up is a FRESH OWNER "
                     "FUNDING DECISION (DESIGN §5.4)."),
    "U-UNREADABLE": ("No statistic from this run is adjudicated, quoted, or cited. The "
                     "failed gate is named with its realized value. U-UNREADABLE IS A "
                     "FULLY ACCEPTABLE OUTCOME."),
}

# ---- READ_RULE §4.3 B — VERBATIM, all nine, on EVERY read-out. ------------- #
HONESTY_RAILS = (
    ("PRIOR-AGAINST 1 — the mass desert",
     "The eps census (K-STRUCTURAL, corroborated on a fresh 31,827-ply read) shows NO "
     "gentle widening exists between exact ties and eps ~= 1.5-2.0: 90% of non-tied tile "
     "plies sit above a quarter-point of leaf preference. THE PLIES THIS PROBE ADDS ARE "
     "ONES WHERE THE LEAF HAS A REAL OPINION."),
    ("PRIOR-AGAINST 2 — \"the vart\"",
     "Tie-triggered search escalation died at its pre-gate (E-FLAT): 2x/4x/10x more search "
     "MOVES tied-ply picks (18/24/31%) but does not IMPROVE them (-0.0094 / +0.0494 / "
     "+0.0502, all below the ratio-0.35 AND z-2 bar; 10x also failed coverage at 0.799). "
     "The tie-arbiter's win is an ORTHOGONAL TERMINAL-GROUNDED SIGNAL BREAKING A PLY WHERE "
     "THE PRIMARY SIGNAL IS EXACTLY ZERO. At a non-tied ply it must instead BEAT AN "
     "11,008-SIM PUCT SEARCH, NOT SILENCE."),
    ("PRIOR-AGAINST 3 — the RND control",
     "Stage-2's matched-compute control read -4.4287 pts/game, -60.09 elo: A LEAF-TIED SET "
     "IS NOT A SET OF INTERCHANGEABLE MOVES, and the champion's own tie-break is far better "
     "than arm-average. The greedy-continuation values carry policy bias that is common-mode "
     "across arms ONLY WHEN THE PRIMARY SIGNAL IS SILENT — which is exactly the condition "
     "this probe removes."),
    ("INCUMBENT ASYMMETRY",
     "The champion's pick IS one of the arms; kappa is capture-vs-incumbent and "
     "NEGATIVE-CAPABLE; kappa = 0 means \"no better than the champion\", NOT \"no signal\"; "
     "and kappa is NOT zero-mean under an uninformative arbiter."),
    ("CURRENCY",
     "scale_all == 1.0; KAPPA IS NOT DIRECTLY COMPARABLE TO THE TIED-PLY arb = +0.2065 "
     "(that number is scale_all-scaled and this one is not; its unscaled discriminable "
     "sibling is +0.2844)."),
    ("OFFLINE CAPTURE HAS UNDER-READ THE GAME CELL ON THIS EXACT AXIS",
     "At tied plies the offline instrument returned P-PARTIAL — not convicted, with a "
     "NEGATIVE blind holdout (-0.0051) — and the Stage-2 game cell then fired G-CONFIRMED at "
     "z_D +8.04. => E-FLATNULL IS A FUNDING VERDICT, NEVER AN EXCLUSION, in the same words "
     "W-FLAT and F-FLAT used. An offline null here does NOT prove the deploy effect is null; "
     "it proves we will not spend a game cell on it."),
    ("BUDGET-EPOCH MISMATCH",
     "The corpus GAMES were generated by the k4x688 / 2752-budget champion; the INCUMBENT "
     "PRICED is whatever PRODUCTION.yaml resolves at run time. Inherited verbatim from "
     "tiletie_pricing_20260812 and unchanged by this design."),
    ("NO DEPLOY IS LICENSED ON ANY BRANCH",
     "rho_phone = 5.520 at B=16 is UNSOLVED for the TIED-ply arbiter already; every-ply "
     "arbitration roughly doubles the fire rate and therefore roughly doubles it again. "
     "DESKTOP-ONLY AT BEST."),
    ("SEC-ARB is circular by construction",
     "The arbiter's picks priced by tier1-greedy itself have capture 1 against their own "
     "headroom. It may NEVER be a branch input, and it is not computed here."),
)

SCOPE_FENCE = (
    "SCOPE FENCE (DESIGN §4.5, BINDING, restated on every branch): a near-tie-only "
    "deployment would need kappa_A >= 1.38 / (1.277 x 0.31) = 3.49 pts/ply against a "
    "tied-ply oracle CEILING of +0.2545 — ~14x the entire oracle headroom of the adjacent "
    "ply class. NO BRANCH, AND NO SUCCESSOR DESIGN, MAY RESCUE A POOLED NULL BY CARVING "
    "OUT STRATUM A, A PHASE BUCKET, OR ANY OTHER SUB-POPULATION.")

SIZE1_LIMITS = (
    "SIZE-1 IS A KILL-ORIENTED SCREEN: good power against the prior-favoured hypothesis "
    "(harm), POOR POWER AGAINST A MODEST GAIN. It buys NO oracle ceiling (`ora`), NO null "
    "level (`rnd`), NO `arm0_leaf` and NO `F` — those need arms the arbiter never selects, "
    "which the §5.2 selective economy does not price. E-FLATNULL is MARGINAL at n = 400 "
    "(it needs kappa_hat <= -0.018 at q = 0.76), so this screen MUST NEVER be described as "
    "\"it will settle it either way\".")

KILL_ONLY_SENTENCE = (
    "READ_RULE §0.A: SIZE-1 funds ONE read point (n = 400) and the plan declares it a "
    "ONE-SIDED, KILL-ONLY FUTILITY INTERIM — it MAY NOT FIRE ANY POSITIVE BRANCH. A "
    "positive kappa_hat at SIZE-1 is an UNRESOLVED READING. This is a DECLARED LIMIT OF "
    "THE FUNDED SIZE, NOT A DISCOVERED ONE, and it must not be narrated after the fact as "
    "\"the probe found nothing positive\".")


def _f(x, nd=4, sign=True):
    if x is None or (isinstance(x, float) and x != x):
        return "None"
    return f"{x:+.{nd}f}" if sign else f"{x:.{nd}f}"


def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


# --------------------------------------------------------------------------- #
# G-KNOWNGOOD — run the subcommand FIRST, refuse on failure                     #
# --------------------------------------------------------------------------- #
def invoke_knowngood(out_dir, python_exe=None, timeout=7200,
                     if_records=None, arb_records=None) -> dict:
    """Run ``probe_pickers.py knowngood`` and return ``{rc, stdout_tail}``.

    A separate process on purpose: it is the tiearb harness's own gate, pinned to
    the OLD corpus's constants, and importing it here would drag those pins into
    this analyser. Tests monkeypatch THIS function — never the gate that reads it.

    ⚠️ EP-D5: ``probe_pickers.py``'s ``--if-records``/``--arb-records`` default to
    LOCAL-BOX literal paths under ``/mnt/c/carc-shared`` (``DEFAULT_IF_RECORDS`` /
    ``analyze_tiearb.DEFAULT_ARB_ROOTS``). This is the SAME bug class EP-D4 fixed
    at the launcher's pre-launch ``gate_knowngood()`` bash call site — a SECOND
    call site, here, that EP-D4 did not cover. ``if_records``/``arb_records`` let
    the caller thread role-resolved (``$SHARE``) roots explicitly, mirroring
    EP-D4's pattern; when both are absent the python-side defaults still fire
    (only correct on the box those defaults name).
    """
    cmd = [python_exe or sys.executable, str(REPO / "scripts/tiletie/probe_pickers.py"),
           "knowngood", "--out-dir", str(out_dir)]
    if if_records:
        cmd += ["--if-records", str(if_records)]
    for root in (arb_records or []):
        cmd += ["--arb-records", str(root)]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           cwd=str(REPO))
        return {"rc": int(p.returncode), "cmd": cmd,
                "stdout_tail": (p.stdout or "")[-2000:],
                "stderr_tail": (p.stderr or "")[-2000:]}
    except Exception as exc:                                       # noqa: BLE001
        return {"rc": 1, "cmd": cmd, "stdout_tail": "",
                "stderr_tail": f"{type(exc).__name__}: {exc}"}


def gate_knowngood(knowngood_dir, knowngood_json=None, python_exe=None,
                   if_records=None, arb_records=None) -> dict:
    """READ_RULE §3 ``G-KNOWNGOOD``. FIRST. Refuses on failure."""
    run = invoke_knowngood(knowngood_dir, python_exe=python_exe,
                           if_records=if_records, arb_records=arb_records)
    path = Path(knowngood_json) if knowngood_json else Path(knowngood_dir) / "KNOWNGOOD.json"
    payload = None
    if path.is_file():
        try:
            payload = json.loads(path.read_text())
        except Exception:                                          # noqa: BLE001
            payload = None
    ok = bool(run["rc"] == 0 and payload is not None and payload.get("ok") is True)
    return {
        "id": "G-KNOWNGOOD", "ok": ok,
        "address": (f"scripts/tiletie/probe_pickers.py knowngood -> "
                    f"{path} ['ok'] == true  (require_knowngood pins arb=+0.2065, "
                    "N_POSITIONS_OF_RECORD=733, N_ROOTS_OF_RECORD=399, tol 1e-9 "
                    "against measurement/tiearb_20260816/READOUT.json; "
                    "record roots threaded via --knowngood-if-records/"
                    "--knowngood-arb-records, EP-D5)"),
        "realized": {"rc": run["rc"], "ok_field": (payload or {}).get("ok"),
                     "reproduced": (payload or {}).get("reproduced"),
                     "delta": (payload or {}).get("delta")},
        "detail": ("ABSENT IS FAIL: a missing or unparseable KNOWNGOOD.json is a FAIL, "
                   "not a skip. If this gate fails NO OTHER NUMBER IN THIS HARNESS MAY "
                   "BE READ." + ("" if ok else f"  stderr: {run['stderr_tail'][-400:]}")),
    }


# --------------------------------------------------------------------------- #
# loading                                                                       #
# --------------------------------------------------------------------------- #
def discover_plan_dirs(plan_dir, pattern) -> list:
    return sorted(p for p in Path(plan_dir).glob(pattern)
                  if (p / "POSITIONS_PLAN.json").is_file())


def merge_plans(dirs) -> tuple:
    """``AT.load_plan`` (REUSED — it asserts the §6-threat-3 dedupe was applied) over
    every chunk dir, merged with an EXPLICIT duplicate-rid check across chunks."""
    arms, plans, dropped, src = {}, [], [], {}
    for d in dirs:
        bundle = AT.load_plan(d)
        dupes = sorted(set(bundle["arms"]) & set(arms))
        if dupes:
            raise SystemExit(f"REFUSING: duplicate rid(s) across plan dirs "
                             f"({src.get(dupes[0])} vs {d}): {dupes[:5]}")
        for rid, meta in bundle["arms"].items():
            arms[rid] = meta
            src[rid] = str(d)
        plans.append({"dir": str(d), **bundle["plan"]})
        dropped.extend(bundle["dropped"].get("rows") or [])
    return arms, plans, dropped


def merge_records(roots, judge) -> tuple:
    """``AT.discover_records`` per root, merged; a duplicate rid ACROSS roots is a
    hard error (the chunks are disjoint by construction)."""
    by_rid, present, not_ok, src = {}, {}, [], {}
    for r in roots:
        root = EC.resolve_records_root(r, judge)
        b, p, nk = AT.discover_records(root)
        dupes = sorted(set(b) & set(by_rid))
        if dupes:
            raise SystemExit(f"REFUSING: duplicate rid(s) across --{judge} roots "
                             f"({src.get(dupes[0])} vs {root}): {dupes[:5]}")
        for rid, legs in b.items():
            by_rid[rid] = legs
            src[rid] = str(root)
        for k, v in p.items():
            present[f"{root}::{k}"] = v
        not_ok.extend(nk)
    return by_rid, present, not_ok


# --------------------------------------------------------------------------- #
# per-position assembly — DESIGN §4.1                                           #
# --------------------------------------------------------------------------- #
def build_rows(arms_index, if_index, arb_by_rid, if_by_rid, parity_base=PARITY_BASE):
    """kappa[p] per position, plus every §3 witness the gates read.

    ⚠️ The ARB matrix is indexed by ARM ORDER; the IF matrix is indexed by ACTION,
    because the §5.2 selective plan prices a SUBSET and therefore renumbers its
    own legs. Joining the two judges on the ACTION (never on the leg index) is
    what makes the subset join exact.
    """
    rows = []
    integ = {j: {"values_a_drift": 0, "seed_drift": 0, "crn_unverified": 0,
                 "checksum_failed": 0, "arm_index_mismatch": 0, "not_ok": 0}
             for j in ("arb", "if")}
    cross = {"compared_rids": 0, "world_seed_mismatch": 0, "playout_seed_mismatch": 0,
             "examples": []}
    counts = {"planned": 0, "absent_arb": 0, "partial_arb": 0, "absent_if_plan": 0,
              "absent_if": 0, "partial_if": 0, "armset_missing_arm": 0,
              "champ_not_arm0": 0, "zerofill_defect": 0, "analysed": 0,
              "priced": 0, "zero": 0, "m_mismatch": 0}

    for rid, meta in sorted(arms_index.items()):
        counts["planned"] += 1
        arms = [int(a) for a in meta["arms"]]
        champ_act = int(meta.get("champ_action", arms[0]))
        if arms[0] != champ_act or int(meta.get("champ_pos", 0)) != 0:
            counts["champ_not_arm0"] += 1          # G-COVER's substrate
        need = list(range(1, len(arms)))
        legs = arb_by_rid.get(rid, {})
        have = sorted(k for k in legs if k in need)
        if not have:
            counts["absent_arb"] += 1
            continue
        if [r for r in need if r not in legs]:
            counts["partial_arb"] += 1
            continue

        ref = legs[have[0]]
        m = int(ref["m"])
        if m != M_EXPECTED:
            counts["m_mismatch"] += 1
        va0 = ref["values_a"]
        for r in have:
            rec = legs[r]
            if rec["values_a"] != va0:
                integ["arb"]["values_a_drift"] += 1
            if (rec["world_seeds"] != ref["world_seeds"]
                    or rec["playout_seeds"] != ref["playout_seeds"]):
                integ["arb"]["seed_drift"] += 1
            if not rec.get("crn_verified"):
                integ["arb"]["crn_unverified"] += 1
            if rec.get("checksum_ok") is False:
                integ["arb"]["checksum_failed"] += 1
            if rec.get("pick_a") != arms[0] or rec.get("pick_b") != arms[r]:
                integ["arb"]["arm_index_mismatch"] += 1
            if not rec.get("ok", False):
                integ["arb"]["not_ok"] += 1
        matrix_arb = [list(va0)] + [list(legs[r]["values_b"]) for r in have]
        arm_order = [0] + have
        acts = [arms[i] for i in arm_order]
        champ_pos = 0

        # ---- DESIGN §4.1: both parity folds; a_arb IS crossfit_regret's a_plus - #
        a_arb_pos, a_arb_act = [], []
        for swap in (False, True):
            sel, eva = AT.parity_indices(m, base=parity_base, swap=swap)
            _h, a_plus = AT.crossfit_regret(matrix_arb, sel, eva, champ_pos)
            a_arb_pos.append(int(a_plus))
            a_arb_act.append(int(acts[int(a_plus)]))
        pickchg_folds = [int(a) != champ_act for a in a_arb_act]

        if_meta = if_index.get(rid)
        if if_meta is None:
            counts["absent_if_plan"] += 1
            continue
        priced_arms = [int(a) for a in if_meta["arms"]]
        zero_planned = len(priced_arms) == 1

        if zero_planned:
            # §5.2 property 1: kappa[p] = 0 IDENTICALLY. Verified, not assumed —
            # the ARB records are on disk, so recompute a_arb and require both
            # folds to BE the champion. That is what makes G-ZEROFILL a gate.
            if any(pickchg_folds):
                counts["zerofill_defect"] += 1
            kappa_folds = [0.0, 0.0]
            priced = False
        else:
            if_legs = if_by_rid.get(rid, {})
            need_if = list(range(1, len(priced_arms)))
            have_if = sorted(k for k in if_legs if k in need_if)
            if not have_if:
                counts["absent_if"] += 1
                continue
            if [r for r in need_if if r not in if_legs]:
                counts["partial_if"] += 1
                continue
            ref_if = if_legs[have_if[0]]
            if int(ref_if["m"]) != m:
                counts["m_mismatch"] += 1
            va0_if = ref_if["values_a"]
            by_action = {int(priced_arms[0]): list(va0_if)}
            for r in have_if:
                rec = if_legs[r]
                if rec["values_a"] != va0_if:
                    integ["if"]["values_a_drift"] += 1
                if (rec["world_seeds"] != ref_if["world_seeds"]
                        or rec["playout_seeds"] != ref_if["playout_seeds"]):
                    integ["if"]["seed_drift"] += 1
                if not rec.get("crn_verified"):
                    integ["if"]["crn_unverified"] += 1
                if rec.get("checksum_ok") is False:
                    integ["if"]["checksum_failed"] += 1
                if rec.get("pick_a") != priced_arms[0] or rec.get("pick_b") != priced_arms[r]:
                    integ["if"]["arm_index_mismatch"] += 1
                if not rec.get("ok", False):
                    integ["if"]["not_ok"] += 1
                by_action[int(priced_arms[r])] = list(rec["values_b"])

            # ---- the CROSS-JUDGE CRN witness (G-CRN). The seeds are
            # sha256(tag|rid|j|salt) -- keyed on rid+salt, NEVER on the arms -- so
            # every leg of one position, in EITHER judge, must see the same M
            # worlds. That is why the comparison is per-rid, not per-leg-index
            # (the selective plan renumbers its own legs).
            cross["compared_rids"] += 1
            if list(ref_if["world_seeds"]) != list(ref["world_seeds"]):
                cross["world_seed_mismatch"] += 1
                if len(cross["examples"]) < 5:
                    cross["examples"].append(f"{rid} world_seeds")
            if list(ref_if["playout_seeds"]) != list(ref["playout_seeds"]):
                cross["playout_seed_mismatch"] += 1
                if len(cross["examples"]) < 5:
                    cross["examples"].append(f"{rid} playout_seeds")

            if champ_act not in by_action or any(a not in by_action for a in a_arb_act):
                counts["armset_missing_arm"] += 1        # G-ARMSET's substrate
                continue
            kappa_folds = []
            for swap, act in zip((False, True), a_arb_act):
                _sel, eva = AT.parity_indices(m, base=parity_base, swap=swap)
                kappa_folds.append(AT._sub_mean(by_action[act], eva)
                                   - AT._sub_mean(by_action[champ_act], eva))
            priced = True

        rows.append({
            "rid": rid, "root_id": str(meta["root_id"]),
            "gap_stratum": meta.get("gap_stratum"), "slice": meta.get("slice"),
            "chunk": meta.get("chunk"), "ply": meta.get("ply"),
            "phase_bucket": meta.get("phase_bucket"), "gap": meta.get("gap"),
            "m": m, "n_arms": len(arms), "n_arms_priced": len(priced_arms),
            "champ_action": champ_act, "arm_order_actions": acts,
            "a_arb_folds": a_arb_act, "a_arb_positions": a_arb_pos,
            "kappa": (kappa_folds[0] + kappa_folds[1]) / 2.0,
            "kappa_fold1": kappa_folds[0], "kappa_fold2": kappa_folds[1],
            "pickchg": bool(any(pickchg_folds)),
            "pickchg_fold1": bool(pickchg_folds[0]),
            "pickchg_fold2": bool(pickchg_folds[1]),
            "priced": bool(priced), "zero_filled": bool(not priced),
            "arm_builder": meta.get("arm_builder"),
            "champ_leaf_hash": meta.get("champ_leaf_hash"),
            "champ_tiearb": meta.get("champ_tiearb"),
            "champ_k_dets": meta.get("champ_k_dets"),
            "champ_sims_per_det": meta.get("champ_sims_per_det"),
            "rules_profile": meta.get("rules_profile"),
            # DESIGN §4.2 — declared currency change, carried per row so no
            # downstream reader can re-apply a tied-ply scaling.
            "scale_all": SCALE_ALL,
        })
        counts["analysed"] += 1
        counts["priced" if priced else "zero"] += 1
    return rows, integ, cross, counts


# --------------------------------------------------------------------------- #
# THE TWO ESTIMATORS — deliberately separate (DESIGN §2.3)                      #
# --------------------------------------------------------------------------- #
def apply_population_weights(rows, w) -> dict:
    """Stamp ``w_scale[p] = w_s / f_hat_s`` on every row and return the realized f_hat.

    mean_p(w_scale[p] * kappa[p]) == SUM_s w_s * mean_{p in s} kappa[p] EXACTLY,
    which is why the pooled estimate can go through ``analyze_tiletie.aggregate``'s
    own ``scale_key`` seam — the identical mechanism the tied-ply analytic zeros
    use — instead of a re-implemented weighted mean.
    """
    n = len(rows)
    counts = Counter(r["gap_stratum"] for r in rows)
    f_hat = {s: (counts.get(s, 0) / n if n else 0.0) for s in STRATA}
    for r in rows:
        s = r["gap_stratum"]
        r["w_scale"] = (w[s] / f_hat[s]) if f_hat.get(s) else 0.0
    return {"n": n, "counts": dict(counts), "f_hat": f_hat, "w": dict(w)}


def kappa_pooled(rows, w, boot_seed) -> dict:
    """PRIMARY. Population-reweighted by the EXACT census ``w`` (known, not estimated).

    ⚠️ THE DESIGN §2.3 STRATIFICATION PENALTY (1.06) BELONGS HERE AND ONLY HERE —
    and it is **realized in the weights**, not multiplied in. ``w_scale`` inflates
    the per-position values of the under-sampled strata, so the cluster-robust se
    computed on those values ALREADY carries the reweighting price. Multiplying by
    1.06 on top would double-count it. ``EP.se_kappa`` (which DOES carry the
    penalty) is reported beside this as the PLANNING figure, never substituted for
    it.
    """
    apply_population_weights(rows, w)
    agg = AT.aggregate(rows, "kappa", "w_scale", seed=boot_seed)
    agg["estimator"] = "pooled (population-reweighted; penalty REALIZED in w_scale)"
    return agg


def kappa_stratum(rows, stratum, boot_seed) -> dict:
    """WITHIN-STRATUM. Reweights nothing, therefore carries NO stratification
    penalty (DESIGN §2.3 / §7.1's ⚠️ SHARPENED note). UNDERPOWERED — SIGN READ AT
    BEST, and NEVER a branch input except through E-FUND/E-CLEAN's
    sign-consistency conjunct."""
    sub = [r for r in rows if r["gap_stratum"] == stratum]
    agg = AT.aggregate(sub, "kappa", None, seed=boot_seed)
    agg["estimator"] = "within-stratum (NO reweighting => NO penalty)"
    agg["label"] = "UNDERPOWERED — SIGN READ AT BEST"
    return agg


def recompute_witness(rows, w) -> dict:
    """READ_RULE §1's from-scratch recomputation. A WITNESS, NEVER A BRANCH INPUT.

    Deliberately does NOT call ``analyze_tiletie``: kappa is rebuilt from the
    per-stratum means (``SUM_s w_s * mean_s`` — the estimand as §1 writes it) and
    the se from a hand-rolled cluster sandwich. Agreement therefore tests the
    weighting identity AND the aggregate plumbing. A disagreement beyond
    ``WITNESS_TOL`` is U-UNREADABLE (§1).
    """
    if not rows:
        return {"kappa": float("nan"), "se": float("nan"), "z": float("nan")}
    by_s = defaultdict(list)
    for r in rows:
        by_s[r["gap_stratum"]].append(float(r["kappa"]))
    kappa = sum(w[s] * _mean(by_s[s]) for s in STRATA if by_s.get(s))
    n = len(rows)
    counts = {s: len(by_s.get(s, ())) for s in STRATA}
    vals = [float(r["kappa"]) * (w[r["gap_stratum"]] * n / counts[r["gap_stratum"]])
            for r in rows]
    ybar = _mean(vals)
    acc = defaultdict(float)
    for v, r in zip(vals, rows):
        acc[r["root_id"]] += v - ybar
    g = len(acc)
    var = (sum(s * s for s in acc.values()) / (n ** 2)) * (g / (g - 1)) if g > 1 else float("nan")
    se = math.sqrt(var) if var == var and var >= 0 else float("nan")
    return {"kappa": kappa, "se": se, "z": (kappa / se) if se else float("nan"),
            "n": n, "n_roots": g,
            "note": "WITNESS ONLY (READ_RULE §1) — never a branch input."}


# --------------------------------------------------------------------------- #
# the holdout — UNTOUCHED until its own gate (DESIGN §6.4 / READ_RULE §4.3 A6)   #
# --------------------------------------------------------------------------- #
class HoldoutGate:
    """kappa_hat on the HOLDOUT roots, computed LAZILY and audited.

    DESIGN §6.4: the holdout enters ``E-FUND`` ONLY as the blind sign-consistency
    conjunct ``kappa_hat_holdout >= 0``. NO OTHER CODE PATH MAY TOUCH IT BEFORE
    ITS GATE: the pooled read (the branch input) never partitions on ``slice``,
    and the §4.3 A6 report is assembled AFTER adjudication.
    ``reads_before_decision`` counts reads taken DURING adjudication — the only
    legitimate one is E-FUND's fourth conjunct, and E-FUND cannot fire at SIZE-1
    (§0.A), so it must read **0** here. The counter is written into the read-out,
    so the discipline is checkable rather than claimed.
    """

    def __init__(self, rows, boot_seed):
        self._rows = [r for r in rows if r.get("slice") == "holdout"]
        self._seed = boot_seed
        self._value = None
        self.reads = 0
        self.reads_before_decision = 0
        self.decided = False

    def decide(self) -> None:
        self.decided = True

    def value(self) -> dict:
        self.reads += 1
        if not self.decided:
            self.reads_before_decision += 1
        if self._value is None:
            self._value = AT.aggregate(self._rows, "kappa", None, seed=self._seed)
            self._value["n_holdout_positions"] = len(self._rows)
            self._value["conjunct_of"] = "E-FUND ONLY (unreachable at SIZE-1, §0.A)"
        return self._value


# --------------------------------------------------------------------------- #
# READ_RULE §3 — the eleven gates                                               #
# --------------------------------------------------------------------------- #
def _gate(gid, ok, address, realized, detail) -> dict:
    return {"id": gid, "ok": bool(ok), "address": address,
            "realized": realized, "detail": detail}


def gate_crn(integ, cross, arb_not_ok, if_not_ok) -> dict:
    bad = (integ["arb"]["crn_unverified"] + integ["if"]["crn_unverified"]
           + integ["arb"]["checksum_failed"] + integ["if"]["checksum_failed"]
           + integ["arb"]["seed_drift"] + integ["if"]["seed_drift"]
           + integ["arb"]["values_a_drift"] + integ["if"]["values_a_drift"]
           + cross["world_seed_mismatch"] + cross["playout_seed_mismatch"]
           + len(arb_not_ok) + len(if_not_ok))
    return _gate(
        "G-CRN", bad == 0,
        "oracle_score_pilot._process fields crn_verified / checksum_ok / world_seeds / "
        "playout_seeds, per record; cross-leg identity per run_tiletie.verify_leg_records; "
        "cross-JUDGE identity per rid (the seeds are sha256(tag|rid|j|salt), keyed on rid, "
        "never on the arms)",
        {"integrity": integ, "cross_judge": cross,
         "arb_records_not_ok": len(arb_not_ok), "if_records_not_ok": len(if_not_ok)},
        "Any record with crn_verified != true or checksum_ok != true, or any seed "
        "divergence between the ARB and clair-puct records of the same rid, VOIDS.")


def gate_cover(counts) -> dict:
    n = counts["champ_not_arm0"]
    return _gate(
        "G-COVER", n == 0,
        "ARMS.json[rid]['champ_pos'] == 0 and arms[0] == champ_action, counted here",
        {"champ_not_arm0": n, "planned": counts["planned"]},
        "0 BY CONSTRUCTION (DESIGN §3.1: the champion's pick IS arm 0), so a nonzero "
        "count is an INSTRUMENT DEFECT — the root_stats_list dedup trap — and NEVER a "
        "finding. This gate is PASS-ALWAYS on a healthy run; READ_RULE §3.1 declares "
        "that acceptable precisely because its only failure mode is a build defect.")


def gate_armset(counts, if_index, arms_index) -> dict:
    """⚠️ SPEC NOTE, declared here rather than resolved silently.

    READ_RULE §3 words ``G-ARMSET`` as "every priced arm present in BOTH judges'
    records, and the two ``arm_order`` lists EQUAL". Under the §5.2 selective
    economy the two ``arm_order`` lists are equal only when all K arms happen to
    be priced; the design's own saving IS that the IF list is a SUBSET. A literal
    string-equality reading would therefore be FAIL-ALWAYS, which READ_RULE §3.1
    forbids by construction. The reading applied — and printed on every branch —
    is the one that makes the gate a real binary:

      (a) every IF-priced arm is present in the ARB plan's arm list for that rid,
      (b) the IF arm list is an ORDER-PRESERVING SUBSEQUENCE of the ARB arm list
          (so arm 0 is the same champion action in both), and
      (c) every arm either fold's a_arb selected was actually priced.
    """
    bad_subset, bad_order = [], []
    for rid, if_meta in sorted(if_index.items()):
        meta = arms_index.get(rid)
        if meta is None:
            bad_subset.append(rid)
            continue
        arms = [int(a) for a in meta["arms"]]
        priced = [int(a) for a in if_meta["arms"]]
        if not set(priced) <= set(arms):
            bad_subset.append(rid)
            continue
        if [a for a in arms if a in set(priced)] != priced:
            bad_order.append(rid)
    ok = (not bad_subset and not bad_order and counts["armset_missing_arm"] == 0)
    return _gate(
        "G-ARMSET", ok,
        "per rid: IF ARMS.json['arms'] subset-of and order-preserving-in ARB "
        "ARMS.json['arms']; every fold's a_arb present in the IF records",
        {"not_a_subset": len(bad_subset), "order_disagreement": len(bad_order),
         "a_arb_not_priced": counts["armset_missing_arm"],
         "examples": (bad_subset + bad_order)[:5]},
        gate_armset.__doc__.strip())


def gate_zerofill(counts, if_index, rows) -> dict:
    n_priced = counts["priced"]
    n_zero = counts["zero"]
    n_analysed = counts["analysed"]
    singleton_ok = all(len(if_index[r["rid"]]["arms"]) == 1
                       for r in rows if r["zero_filled"])
    ok = (n_priced + n_zero == n_analysed and singleton_ok
          and counts["zerofill_defect"] == 0)
    return _gate(
        "G-ZEROFILL", ok,
        "READOUT.json: n_priced + n_zero == n_analysed; every zero-filled rid has "
        "len(arms_to_price) == 1; and (checked here, not assumed) BOTH parity folds' "
        "recomputed a_arb ARE the champion arm on every zero-filled position",
        {"n_priced": n_priced, "n_zero": n_zero, "n_analysed": n_analysed,
         "singleton_ok": bool(singleton_ok),
         "zerofill_defect": counts["zerofill_defect"]},
        "THE ONE GATE THAT GUARDS THE §5.2 ECONOMY'S UNBIASEDNESS: un-priced positions "
        "enter the mean as EXACT ZEROS and enter n and the cluster structure. A "
        "dropped-instead-of-zero-filled position breaks it.")


def gate_distinct(plans) -> dict:
    n_planned = sum(int((p.get("everyply") or {}).get("n_planned", 0)) for p in plans)
    n_dropped = sum(int((p.get("everyply") or {}).get("n_dropped_lt2_distinct", 0))
                    for p in plans)
    rate = (n_dropped / n_planned) if n_planned else 1.0
    return _gate(
        "G-DISTINCT", n_planned > 0 and rate <= G_DISTINCT_MAX,
        "positions_chunk*/POSITIONS_PLAN.json ['everyply']['n_dropped_lt2_distinct'] / "
        "['n_planned'] <= 0.10 (mirrored in CORPUS_SUMMARY.json)",
        {"n_planned": n_planned, "n_dropped_lt2_distinct": n_dropped, "rate": rate,
         "bar": G_DISTINCT_MAX},
        "Dropped positions are COUNTED AND REPORTED IN EVERY CASE. ⚠️ If this fires, the "
        "correct reading is \"the frame is not what the census implied\", NOT \"the lever "
        "failed\".")


def gate_frame(plan_summary, frame, selection=None, holdout_games=None,
               rows=None) -> dict:
    """``G-FRAME`` — the realized draw IS the committed draw.

    The two published conjuncts (``max_abs_f_deviation_pp`` and the census ``w``)
    plus, when the launcher hands them over, a per-row check of the analysed
    corpus against the COMMITTED ``SELECTION.jsonl`` and ``HOLDOUT_GAMES.json``:
    a rid that is not in the committed selection, a stratum stamp that disagrees
    with it, or a dev/holdout slice that disagrees with the seeded ROOT split is
    the realized draw diverging from the committed one — which is exactly this
    gate's proposition, and it is the only place those two launcher arguments are
    load-bearing rather than decorative.
    """
    dev = plan_summary.get("max_abs_f_deviation_pp")
    w_plan = plan_summary.get("population_weights_w") or {}
    w_census = {s: frame["population"]["strata"][s]["share_of_nontied"] for s in STRATA}
    w_ok = all(abs(float(w_plan.get(s, -1)) - w_census[s]) <= 1e-12 for s in STRATA)
    extra = {}
    sel_ok = True
    if selection is not None and rows is not None:
        by_rid = {r["rid"]: r for r in selection}
        hold = set(holdout_games or [])
        off_plan = [r["rid"] for r in rows if r["rid"] not in by_rid]
        bad_stratum = [r["rid"] for r in rows if r["rid"] in by_rid
                       and by_rid[r["rid"]]["stratum"] != r["gap_stratum"]]
        bad_slice = []
        if holdout_games is not None:
            bad_slice = [r["rid"] for r in rows if r["rid"] in by_rid
                         and r["slice"] != ("holdout"
                                            if by_rid[r["rid"]]["game_id"] in hold
                                            else "dev")]
        sel_ok = not (off_plan or bad_stratum or bad_slice)
        extra = {"rids_off_the_committed_selection": len(off_plan),
                 "stratum_stamp_disagreements": len(bad_stratum),
                 "slice_disagreements_vs_HOLDOUT_GAMES": len(bad_slice),
                 "examples": (off_plan + bad_stratum + bad_slice)[:5]}
    ok = (dev is not None and float(dev) <= G_FRAME_MAX_PP and w_ok and sel_ok)
    return _gate(
        "G-FRAME", ok,
        "PLAN_SUMMARY.json['max_abs_f_deviation_pp'] <= 3.0 AND "
        "PLAN_SUMMARY.json['population_weights_w'] == FRAME.json['population']"
        "['strata'][s]['share_of_nontied'] (both emitted by build_everyply_plan.py); "
        "plus every analysed rid / stratum / dev-holdout slice against the committed "
        "SELECTION.jsonl + HOLDOUT_GAMES.json when they are supplied",
        {"max_abs_f_deviation_pp": dev, "bar": G_FRAME_MAX_PP,
         "w_plan": w_plan, "w_census": w_census, "w_equal": bool(w_ok), **extra},
        "A mis-seeded or hand-edited draw genuinely fails; the committed draw's realized "
        "deviation is 0.111 pp against a 3 pp bar (~27x margin). ⚠️ No game may straddle "
        "the dev/holdout boundary — the CLUSTER is the unit (DESIGN §6.4).")


def gate_n(n_analysed, n_priced_planned=N_PRICED_PLANNED) -> dict:
    floor = int(G_N_FRACTION * n_priced_planned)
    return _gate(
        "G-N", n_analysed >= floor,
        f"READOUT.json['n_analysed'] >= {G_N_FRACTION} * {n_priced_planned} = {floor}",
        {"n_analysed": n_analysed, "floor": floor},
        "A partial run is DESIGNED to be readable at its realized n (DESIGN §2.4) down "
        "to this floor — at CHUNK granularity only, never line granularity.")


def gate_epoch(rows, plans, arb_by_rid, if_by_rid) -> dict:
    leaf_hashes = {r.get("champ_leaf_hash") for r in rows}
    profiles = set()
    for by_rid in (arb_by_rid, if_by_rid):
        for legs in by_rid.values():
            for rec in legs.values():
                profiles.add(rec.get("rules_profile"))
    plan_profiles = {p.get("rules_profile") for p in plans if p.get("rules_profile")}
    ok = (leaf_hashes == {LEAF_HASH_OF_RECORD}
          and profiles <= {RULES_PROFILE_OF_RECORD}
          and profiles == {RULES_PROFILE_OF_RECORD}
          and plan_profiles <= {RULES_PROFILE_OF_RECORD})
    return _gate(
        "G-EPOCH", ok,
        "governance/PRODUCTION.yaml champion.leaf_hash (THE harness_leaf_hash DIALECT) "
        f"== {LEAF_HASH_OF_RECORD}, stamped per row as ARMS.json[rid]['champ_leaf_hash']; "
        "every leg record's rules_profile == 'walled'",
        {"leaf_hashes_seen": sorted(x for x in leaf_hashes if x is not None),
         "expected": LEAF_HASH_OF_RECORD,
         "rules_profiles_seen": sorted(x for x in profiles if x is not None),
         "plan_rules_profiles": sorted(x for x in plan_profiles if x is not None)},
        "⚠️ NAMING THE DIALECT IS LOAD-BEARING. The corpus games stamp "
        "leaf_hash_runtime = 6dfffd57051690f2, which is the frozen_config_hash_meeple_k0 "
        "DIALECT OF THE SAME LEAF whose harness dialect is a36d2e15a3b3d71d. A gate "
        "comparing those two strings would be FAIL-ALWAYS on a healthy run (READ_RULE "
        "§3.1's ⚠️ SHARPENED row).")


def gate_champ(rows) -> dict:
    k = {r.get("champ_k_dets") for r in rows}
    s = {r.get("champ_sims_per_det") for r in rows}
    t = {r.get("champ_tiearb") for r in rows}
    b = {r.get("arm_builder") for r in rows}
    ok = len(k) == 1 and len(s) == 1 and len(t) == 1 and len(b) == 1 and None not in k
    return _gate(
        "G-CHAMP", ok,
        "the resolved agent's own fair_deploy.k_dets / .sims_per_det AND the resolved "
        "tiearb block {enabled,B,J,mode,salt,eps}, stamped on every row "
        "(ARMS.json[rid]['champ_k_dets'|'champ_sims_per_det'|'champ_tiearb']) and CONSTANT",
        {"k_dets": sorted(x for x in k if x is not None),
         "sims_per_det": sorted(x for x in s if x is not None),
         "tiearb": sorted(x for x in t if x is not None),
         "arm_builder": sorted(x for x in b if x is not None)},
        "⚠️ ADDRESS NOTE: the tiearb block is read from governance/PRODUCTION.yaml "
        "(champion.fair_deploy.tiearb), NOT from the built agent's manifest — "
        "make_production_champion takes tiearb as a KEYWORD and champ_picks."
        "champion_search_pick (the DESIGN §6.3 mandated seam) does not pass it, so "
        "manifest['cand_tiearb'] is absent by construction. At a NON-TIED ply this is "
        "behaviourally inert: detect_tie is false at eps = 0.0.")


READ_RULE_SECTION4_START = "## §4 — THE BRANCHES"
READ_RULE_SECTION4_END = "## §5 —"


def _section4(text: str) -> str:
    i = text.find(READ_RULE_SECTION4_START)
    j = text.find(READ_RULE_SECTION4_END)
    return text[i:j] if (i >= 0 and j > i) else ""


def _git(*args, cwd=REPO):
    p = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def gate_blind(blind_commit_path, pair_dir, if_records_roots) -> dict:
    """``G-BLIND`` — the pre-registration really preceded the numbers."""
    problems, realized = [], {}
    p = Path(blind_commit_path)
    sha = p.read_text().strip() if p.is_file() else ""
    realized["blind_commit"] = sha
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        problems.append("BLIND_COMMIT is missing or is not 40 hex chars (a placeholder "
                        "counts as ABSENT, and ABSENT IS FAIL)")
    design = Path(pair_dir) / "DESIGN.md"
    rr = Path(pair_dir) / "READ_RULE.md"
    if not problems:
        for f in (design, rr):
            rel = f.resolve().relative_to(REPO)
            rc, _ = _git("cat-file", "-e", f"{sha}:{rel}")
            if rc != 0:
                problems.append(f"{rel} does not exist at BLIND_COMMIT {sha[:12]}")
        rc, ts = _git("show", "-s", "--format=%ct", sha)
        realized["blind_commit_unixtime"] = int(ts) if rc == 0 and ts else None
        if rc != 0:
            problems.append(f"BLIND_COMMIT {sha[:12]} is not a commit in this repo")
    # §4 byte-identical across revisions
    if not problems:
        rel = rr.resolve().relative_to(REPO)
        rc, out = _git("show", f"{sha}:{rel}")
        base = _section4(out) if rc == 0 else ""
        realized["section4_bytes"] = len(base)
        if not base:
            problems.append("could not extract READ_RULE §4 at BLIND_COMMIT")
        else:
            if _section4(rr.read_text()) != base:
                problems.append("READ_RULE §4 in the WORKING TREE differs from §4 at "
                                "BLIND_COMMIT — §4 IS NOT EDITED POST HOC")
            rc, revs = _git("log", "--format=%H", f"{sha}..HEAD", "--", str(rel))
            for rev in [r for r in revs.splitlines() if r.strip()]:
                rc2, txt = _git("show", f"{rev}:{rel}")
                if rc2 == 0 and _section4(txt) != base:
                    problems.append(f"READ_RULE §4 changed in revision {rev[:12]}")
            realized["revisions_since_blind_commit"] = len(
                [r for r in revs.splitlines() if r.strip()])
    # the pre-registration precedes the FIRST PRICING leg record
    first = None
    for root in if_records_roots:
        rt = EC.resolve_records_root(root, "clair-puct")
        for f in Path(rt).rglob("records/*.json"):
            mt = f.stat().st_mtime
            first = mt if first is None else min(first, mt)
    realized["first_pricing_record_mtime"] = first
    if first is None:
        problems.append("no clair-puct (PRICING) record found — nothing to order against")
    elif realized.get("blind_commit_unixtime") and first < realized["blind_commit_unixtime"]:
        problems.append("a PRICING leg record predates BLIND_COMMIT — the blind ordering "
                        "was violated")
    return _gate(
        "G-BLIND", not problems,
        "git history: the commit introducing DESIGN.md + READ_RULE.md precedes the first "
        "clair-puct (PRICING) leg record; BLIND_COMMIT holds that sha; READ_RULE §4 is "
        "byte-identical across every revision since",
        {**realized, "problems": problems},
        "The launcher hard-refuses without a real 40-hex BLIND_COMMIT, and git history is "
        "checkable independently of any number.")


def run_gates(*, knowngood, integ, cross, arb_not_ok, if_not_ok, counts, if_index,
              arms_index, rows, plans, plan_summary, frame, arb_by_rid, if_by_rid,
              blind_commit, pair_dir, if_roots, n_priced_planned,
              selection=None, holdout_games=None) -> list:
    """Every §3 gate, in READ_RULE table order. G-KNOWNGOOD is ALWAYS FIRST."""
    return [
        knowngood,
        gate_crn(integ, cross, arb_not_ok, if_not_ok),
        gate_cover(counts),
        gate_armset(counts, if_index, arms_index),
        gate_zerofill(counts, if_index, rows),
        gate_distinct(plans),
        gate_frame(plan_summary, frame, selection, holdout_games, rows),
        gate_n(counts["analysed"], n_priced_planned),
        gate_epoch(rows, plans, arb_by_rid, if_by_rid),
        gate_champ(rows),
        gate_blind(blind_commit, pair_dir, if_roots),
    ]


# --------------------------------------------------------------------------- #
# READ_RULE §4 — the branch table, IN ORDER, FIRST MATCH WINS                    #
# --------------------------------------------------------------------------- #
def decide_branch(kappa, se, z, stratum_means, holdout_gate, *, kill_only=True) -> dict:
    """§4, read in order; the FIRST whose condition holds is the branch, taken
    VERBATIM — subject to §0.A, which STRUCTURALLY BLOCKS E-CLEAN and E-FUND at
    SIZE-1 and falls them through to the next branch.

    ⚠️ The holdout is not touched unless E-FUND's first three conjuncts hold AND
    the branch is not blocked; at SIZE-1 it is always blocked, so the holdout is
    never a branch input here (it is still REPORTED — §4.3 A item 6).
    """
    ub95 = kappa + UB95_K * se if se == se else float("nan")
    signs_ok = sum(1 for s in STRATA
                   if stratum_means.get(s) is not None and stratum_means[s] >= 0) >= 2
    conj = {
        "E-HARM": {"kappa_le_-0.15": kappa <= KAPPA_HARM, "z_le_-2": z <= -Z_BAR},
        "E-CLEAN": {"kappa_ge_0.35": kappa >= KAPPA_CLEAN, "z_ge_2": z >= Z_BAR,
                    "ge2of3_strata_nonneg": signs_ok},
        "E-FUND": {"kappa_ge_0.15": kappa >= KAPPA_STAR, "z_ge_2": z >= Z_BAR,
                   "ge2of3_strata_nonneg": signs_ok},
        "E-FLATNULL": {"UB95_lt_0.15": ub95 < KAPPA_STAR},
    }
    blocked, fired = [], None
    for name in BRANCH_ORDER:
        if name == "E-UNRESOLVED":
            fired = name
            break
        cond = all(conj[name].values())
        if name == "E-FLATNULL":
            cond = cond and not all(conj["E-HARM"].values())
            conj["E-FLATNULL"]["not_E-HARM"] = not all(conj["E-HARM"].values())
        if name == "E-FUND" and cond and not (kill_only and name in KILL_ONLY_BLOCKED):
            hv = holdout_gate.value()
            hk = hv.get("mean")
            conj["E-FUND"]["kappa_holdout_ge_0"] = bool(hk is not None and hk >= 0)
            cond = cond and conj["E-FUND"]["kappa_holdout_ge_0"]
        if not cond:
            continue
        if kill_only and name in KILL_ONLY_BLOCKED:
            blocked.append(name)
            continue
        fired = name
        break
    holdout_gate.decide()
    return {
        "branch": fired, "conjuncts": conj, "blocked_by_section_0A": blocked,
        "kill_only_interim": bool(kill_only),
        "ub95": ub95, "ub95_convention": "kappa_hat + 2.0 * se (READ_RULE §1)",
        "strata_nonneg_count": sum(1 for s in STRATA
                                   if stratum_means.get(s) is not None
                                   and stratum_means[s] >= 0),
        "licence": BRANCH_LICENCE[fired],
        "section_0A": KILL_ONLY_SENTENCE,
    }


# --------------------------------------------------------------------------- #
# §4.3 A — the derived prints                                                   #
# --------------------------------------------------------------------------- #
def elo_chain(kappa) -> dict:
    """DESIGN §4.3 — a BRACKET, never a point, and the +23.92 Stage-2 headline may
    NEVER be quoted bare (its winrate z is +1.94, below 2: the margin convicts,
    the win-rate does not)."""
    out = {}
    for tag, na in (("conservative_NA_0.31", NA_BRACKET[0]),
                    ("optimistic_NA_0.85", NA_BRACKET[1])):
        pts = kappa * PLIES_PER_GAME * na
        out[tag] = {
            "NA": na, "pts_per_game": pts, "elo": ELO_PER_PTS_GAME * pts,
            # §4.4: printed MECHANICALLY so no branch can imply an unfunded cell
            # is cheap. n=800 resolves 1.38 pts/game at 2 sigma.
            "n_cell": (CELL_N * (CELL_RESOLVES_PTS / pts) ** 2) if pts else None,
        }
    out["rider"] = ("The +23.92 elo Stage-2 headline MAY NEVER BE QUOTED BARE (winrate "
                    "z = +1.94 < 2). THE MARGIN CONVICTS; THE WIN-RATE DOES NOT. The same "
                    "rider applies to every elo image above, on every branch. Elo is a "
                    "DERIVED DISPLAY QUANTITY ONLY — never the unit a bar is set in.")
    return out


def n_to_resolve(kappa, se, n_analysed) -> dict:
    """READ_RULE §4 branch 5's MANDATORY print: the n that would resolve the
    OBSERVED kappa_hat at the REALIZED dispersion (se scales as 1/sqrt(n))."""
    if not kappa or se != se or se <= 0:
        return {"n": None, "why": "kappa_hat is 0 or the se is undefined"}
    n = n_analysed * (Z_BAR * se / abs(kappa)) ** 2
    return {"n": n, "n_ceil": int(math.ceil(n)), "realized_se": se,
            "realized_n": n_analysed,
            "why": ("n such that |kappa_hat| / se(n) = 2.0 at the REALIZED dispersion; "
                    "se(n) = se_realized * sqrt(n_realized / n). ⚠️ A top-up is a FRESH "
                    "OWNER FUNDING DECISION (DESIGN §5.4) and the corpus's maximum "
                    "constructible supply is 449 games x cap 2 = 898 positions.")}


def phi_nontied(plans) -> dict:
    """The realized deployed fire rate: arbitrable non-tied plies per game AFTER
    dedup (DESIGN §4.6 companion `phi_nontied`)."""
    n_planned = sum(int((p.get("everyply") or {}).get("n_planned", 0)) for p in plans)
    n_dropped = sum(int((p.get("everyply") or {}).get("n_dropped_lt2_distinct", 0))
                    for p in plans)
    keep = (1.0 - n_dropped / n_planned) if n_planned else float("nan")
    return {"nontied_per_game_census": 2 * PLIES_PER_GAME,
            "kept_fraction_after_dedupe": keep,
            "phi_nontied_per_game": 2 * PLIES_PER_GAME * keep,
            "phi_nontied_per_game_per_seat": PLIES_PER_GAME * keep}


def q_block(rows) -> dict:
    """`q` = `pickchg` per fold, pooled and per stratum. With `phi_nontied` and the
    realized se these are THE THREE QUANTITIES THAT RE-PRICE ANY TOP-UP."""
    def frac(rs, key):
        return (sum(1 for r in rs if r[key]) / len(rs)) if rs else None
    out = {"pooled": frac(rows, "pickchg"),
           "fold1": frac(rows, "pickchg_fold1"),
           "fold2": frac(rows, "pickchg_fold2"),
           "by_stratum": {s: frac([r for r in rows if r["gap_stratum"] == s], "pickchg")
                          for s in STRATA},
           "planning_central": 0.76}
    q = out["pooled"]
    out["flatnull_reachability"] = {
        "q_realized": q,
        "note": ("READ_RULE §4's ⚠️ note: E-FLATNULL needs kappa_hat < 0.15 - 2*se. If "
                 "the realized q came in BELOW the planning-central 0.76 the bound "
                 "tightens and E-FLATNULL opens up; if q ran high it closes further. "
                 "This is printed so the reachability condition is CHECKABLE rather "
                 "than inferred."),
        "planned_se_at_realized_q": (EP.se_kappa(len(rows), q)
                                     if rows and q else None),
    }
    return out


# --------------------------------------------------------------------------- #
# assembly                                                                      #
# --------------------------------------------------------------------------- #
def build_readout(args) -> dict:
    pair_dir = Path(args.plan_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # ⛔ G-KNOWNGOOD FIRST — nothing else in this harness may be read until it passes.
    kg = gate_knowngood(args.knowngood_dir or out_dir, args.knowngood, args.python_exe,
                       args.knowngood_if_records, args.knowngood_arb_records)

    pos_dirs = ([Path(d) for d in args.positions_dir] if args.positions_dir
                else discover_plan_dirs(pair_dir, args.positions_glob))
    if_dirs = ([Path(d) for d in args.if_positions_dir] if args.if_positions_dir
               else discover_plan_dirs(pair_dir, args.if_positions_glob))
    if not pos_dirs or not if_dirs:
        raise SystemExit(f"REFUSING: no positions dirs under {pair_dir} "
                         f"(arms glob {args.positions_glob!r}, "
                         f"IF glob {args.if_positions_glob!r})")
    arms_index, plans, _dropped = merge_plans(pos_dirs)
    if_index, if_plans, _ = merge_plans(if_dirs)

    arb_by_rid, arb_present, arb_not_ok = merge_records(args.arb_records, "tier1-greedy")
    if_by_rid, if_present, if_not_ok = merge_records(args.if_records, "clair-puct")

    rows, integ, cross, counts = build_rows(arms_index, if_index, arb_by_rid, if_by_rid,
                                            args.parity_base)
    frame = json.loads((pair_dir / "FRAME.json").read_text())
    plan_summary = json.loads((pair_dir / "PLAN_SUMMARY.json").read_text())
    w = {s: frame["population"]["strata"][s]["share_of_nontied"] for s in STRATA}

    # The COMMITTED draw, for G-FRAME's per-row conjunct. Optional inputs: absent
    # simply means the gate checks its two published conjuncts and nothing more.
    selection = None
    if args.selection and Path(args.selection).is_file():
        selection = [json.loads(x) for x
                     in Path(args.selection).read_text().splitlines() if x.strip()]
    holdout_games = None
    if args.holdout_games and Path(args.holdout_games).is_file():
        holdout_games = json.loads(Path(args.holdout_games).read_text()).get("holdout")

    gates = run_gates(knowngood=kg, integ=integ, cross=cross, arb_not_ok=arb_not_ok,
                      if_not_ok=if_not_ok, counts=counts, if_index=if_index,
                      arms_index=arms_index, rows=rows, plans=plans,
                      plan_summary=plan_summary, frame=frame, arb_by_rid=arb_by_rid,
                      if_by_rid=if_by_rid, blind_commit=args.blind_commit,
                      pair_dir=pair_dir, if_roots=args.if_records,
                      n_priced_planned=args.n_priced_planned,
                      selection=selection, holdout_games=holdout_games)

    pooled = kappa_pooled(rows, w, args.boot_seed) if rows else {}
    strata = {s: (kappa_stratum(rows, s, args.boot_seed) if rows else {}) for s in STRATA}
    witness = recompute_witness(rows, w)
    kappa = pooled.get("mean")
    se = pooled.get("se_cluster")
    z = pooled.get("z")

    # READ_RULE §1: the witness is a PRECONDITION (a disagreement beyond floating-
    # point tolerance is U-UNREADABLE) but NEVER a branch input. It is reported
    # separately from the eleven §3 gates because §1, not §3, declares it.
    wit_ok = bool(kappa is not None and se is not None
                  and abs(witness["kappa"] - kappa) <= WITNESS_TOL
                  and abs(witness["se"] - se) <= WITNESS_TOL)
    witness_gate = _gate(
        "WITNESS (READ_RULE §1)", wit_ok,
        "a from-scratch recomputation of kappa (SUM_s w_s * mean_s) and of the cluster "
        "sandwich, computed WITHOUT analyze_tiletie, printed beside the analyser's own",
        {"witness": {k: witness.get(k) for k in ("kappa", "se", "z", "n", "n_roots")},
         "analyser": {"kappa": kappa, "se": se, "z": z}, "tol": WITNESS_TOL},
        "A disagreement beyond floating-point tolerance is U-UNREADABLE (§1). THE "
        "RECOMPUTATION IS A WITNESS, NEVER A BRANCH INPUT.")

    holdout = HoldoutGate(rows, args.boot_seed)
    all_ok = all(g["ok"] for g in gates) and wit_ok
    if all_ok and rows:
        adj = decide_branch(kappa, se, z, {s: strata[s].get("mean") for s in STRATA},
                            holdout, kill_only=args.kill_only)
    else:
        holdout.decide()
        failed = [g["id"] for g in gates if not g["ok"]] + ([] if wit_ok else ["WITNESS"])
        adj = {"branch": "U-UNREADABLE", "conjuncts": {},
               "blocked_by_section_0A": [], "kill_only_interim": bool(args.kill_only),
               "failed_gates": failed, "licence": BRANCH_LICENCE["U-UNREADABLE"],
               "section_0A": KILL_ONLY_SENTENCE}

    hold = holdout.value()                     # reported on EVERY branch (§4.3 A6)
    n = counts["analysed"]
    verdict = {
        "schema": SCHEMA, "run_id": RUN_ID, "design_doc": DESIGN_DOC,
        "read_rule": READ_RULE_DOC,
        "branch": adj["branch"], "adjudication": adj,
        "primary": {
            "kappa": kappa, "se_cluster": se, "z_kappa": z,
            "ub95": adj.get("ub95"),
            "n_analysed": n, "n_priced": counts["priced"], "n_zero": counts["zero"],
            "n_roots": pooled.get("n_roots"),
            "boot_lo": pooled.get("boot_lo"), "boot_hi": pooled.get("boot_hi"),
            "sd_positions": pooled.get("sd_positions"),
            "unit": "points of final-score margin per NON-TIED TILE PLY, root seat",
            "scale_all": SCALE_ALL,
            "planning_se_at_n_and_q": (
                EP.se_kappa(n, q_block(rows)["pooled"])
                if rows and q_block(rows)["pooled"] else None),
            "planning_se_note": ("EP.se_kappa CARRIES the DESIGN §2.3 penalty and is a "
                                 "PLANNING figure. The REALIZED se above already carries "
                                 "the reweighting price inside w_scale — it is NOT "
                                 "multiplied by 1.06 again."),
        },
        "witness": witness, "witness_gate": witness_gate,
        "per_stratum": {s: {**strata[s], "planning_se_within_stratum": (
            EP.se_kappa_stratum(strata[s].get("n") or 1, 0.76))} for s in STRATA},
        "q": q_block(rows) if rows else {},
        "phi_nontied": phi_nontied(plans),
        "elo_chain": elo_chain(kappa) if kappa is not None else {},
        "n_to_resolve": (n_to_resolve(kappa, se, n) if kappa is not None else {}),
        "holdout": {**hold, "reads_before_decision": holdout.reads_before_decision,
                    "note": ("DESIGN §6.4 — a ROOT split drawn BEFORE any position and "
                             "BEFORE any leg. It enters E-FUND ONLY as the blind "
                             "sign-consistency conjunct, and E-FUND CANNOT FIRE AT "
                             "SIZE-1 (§0.A). ⚠️ THE BRANCH INPUT IS THE POOLED READ. The "
                             "tiearb precedent is also the warning: its pooled read fired "
                             "every conjunct EXCEPT C_h on a 211-position holdout of "
                             "-0.0051; this holdout is smaller still.")},
        "gates": gates,
        "counts": counts, "integrity": integ, "cross_judge_crn": cross,
        "arm_builder": sorted({r.get("arm_builder") for r in rows} - {None}),
        "champion": sorted({r.get("champ_tiearb") for r in rows} - {None}),
        "champion_k_dets": sorted({r.get("champ_k_dets") for r in rows} - {None}),
        "champion_sims_per_det": sorted({r.get("champ_sims_per_det") for r in rows} - {None}),
        "rules_profiles": sorted({r.get("rules_profile") for r in rows} - {None}),
        "records_present": {"arb": arb_present, "if": if_present},
        "plan_dirs": [str(d) for d in pos_dirs],
        "if_plan_dirs": [str(d) for d in if_dirs],
        "code_rev": _git("rev-parse", "--short", "HEAD")[1],
        "band": EC.BAND, "corpus": EC.CORPUS,
        "governance": ("0 games on every branch. NO deck band, NO BAND_REGISTRY row, NO "
                       "claim id, NO experiments/results.csv row, PRODUCTION.yaml "
                       "UNTOUCHED — regardless of outcome (READ_RULE §0 / BAND_NOTE.md). "
                       "⚠️ No number from this probe may be POOLED with any statistic "
                       "from another band (CL-068)."),
        "honesty_rails": [{"title": t, "text": x} for t, x in HONESTY_RAILS],
        "scope_fence": SCOPE_FENCE, "size1_limits": SIZE1_LIMITS,
        "truncation": {
            "chunks_seen": sorted({r.get("chunk") for r in rows} - {None}),
            "note": ("§4.3 D — if fewer than 4 chunks completed, the completed-chunk "
                     "prefix is a uniform random subsample AT CHUNK GRANULARITY, never "
                     "line granularity, and G-N is re-checked at the realized n."),
        },
    }
    return verdict, rows


# --------------------------------------------------------------------------- #
# rendering                                                                     #
# --------------------------------------------------------------------------- #
def render(v: dict) -> str:
    p = v["primary"]
    L = []
    L.append(f"# EVERY-PLY ROLLOUT ARBITRATION (SIZE-1) — READ-OUT: **{v['branch']}**")
    L.append("")
    L.append(f"Run `{v['run_id']}` · design [`DESIGN.md`](DESIGN.md) · "
             f"read-rule [`READ_RULE.md`](READ_RULE.md) · code `{v['code_rev']}`")
    L.append("")
    L.append(f"> **{v['branch']}** — {v['adjudication']['licence']}")
    L.append("")
    if v["adjudication"].get("blocked_by_section_0A"):
        L.append(f"> ⛔ **§0.A BLOCKED**: "
                 f"{', '.join(v['adjudication']['blocked_by_section_0A'])} met its "
                 f"condition and was STRUCTURALLY BLOCKED by the kill-only declaration; "
                 f"the read fell through to **{v['branch']}**.")
        L.append("")
    L.append(v["adjudication"]["section_0A"])
    L.append("")
    L.append("## §4.3 A — the numbers")
    L.append("")
    L.append(f"- `kappa_hat` = **{_f(p['kappa'])}** pts / non-tied tile ply "
             f"· `se` {_f(p['se_cluster'], sign=False)} · `z_kappa` {_f(p['z_kappa'])} "
             f"· `UB95` {_f(p['ub95'])}")
    L.append(f"- `n_analysed` {p['n_analysed']} = `n_priced` {p['n_priced']} + "
             f"`n_zero` {p['n_zero']} · `n_roots` {p['n_roots']}")
    L.append(f"- bootstrap 95% [{_f(p['boot_lo'])}, {_f(p['boot_hi'])}] · "
             f"sd(positions) {_f(p['sd_positions'], sign=False)}")
    L.append(f"- planning se at the realized (n, q): "
             f"{_f(p['planning_se_at_n_and_q'], sign=False)} — {p['planning_se_note']}")
    w = v["witness"]
    L.append(f"- **WITNESS (§1)**: from-scratch `kappa` {_f(w['kappa'])} · `se` "
             f"{_f(w['se'], sign=False)} · `z` {_f(w['z'])} — "
             f"{'AGREES' if v['witness_gate']['ok'] else 'DISAGREES ⇒ U-UNREADABLE'} "
             f"(tol {WITNESS_TOL:g}). A WITNESS, NEVER A BRANCH INPUT.")
    L.append("")
    L.append("### per stratum — ⚠️ UNDERPOWERED, SIGN READ AT BEST, never a branch "
             "input except through E-FUND/E-CLEAN's sign-consistency conjunct")
    L.append("")
    L.append("| stratum | n | kappa_hat | se (within, NO penalty) | planning se |")
    L.append("|---|---:|---:|---:|---:|")
    for s in STRATA:
        b = v["per_stratum"][s]
        L.append(f"| {s} | {b.get('n')} | {_f(b.get('mean'))} | "
                 f"{_f(b.get('se_cluster'), sign=False)} | "
                 f"{_f(b.get('planning_se_within_stratum'), sign=False)} |")
    L.append("")
    q = v["q"]
    L.append(f"- `q` (`pickchg`) pooled **{_f(q.get('pooled'), 4, False)}** · fold1 "
             f"{_f(q.get('fold1'), 4, False)} · fold2 {_f(q.get('fold2'), 4, False)} · "
             f"by stratum {q.get('by_stratum')} (planning-central 0.76)")
    L.append(f"- `phi_nontied` {_f(v['phi_nontied']['phi_nontied_per_game'], 3, False)} "
             f"non-tied plies/game after dedupe "
             f"({_f(v['phi_nontied']['phi_nontied_per_game_per_seat'], 3, False)} per seat)")
    L.append(f"- E-FLATNULL reachability: {q.get('flatnull_reachability', {}).get('note')}")
    L.append("")
    L.append("### the elo chain — a BRACKET, never a point")
    L.append("")
    L.append("| NA | pts/game | elo image | implied `n_cell` |")
    L.append("|---|---:|---:|---:|")
    for tag in ("conservative_NA_0.31", "optimistic_NA_0.85"):
        e = v["elo_chain"].get(tag)
        if e:
            L.append(f"| {e['NA']} | {_f(e['pts_per_game'], 3)} | {_f(e['elo'], 1)} | "
                     f"{('%.0f' % e['n_cell']) if e['n_cell'] else 'n/a'} |")
    L.append("")
    L.append(v["elo_chain"].get("rider", ""))
    L.append("")
    ntr = v["n_to_resolve"]
    L.append(f"- **n that would resolve the observed `kappa_hat`** at the REALIZED "
             f"dispersion: **{ntr.get('n_ceil')}** positions — {ntr.get('why')}")
    h = v["holdout"]
    L.append(f"- `kappa_hat_holdout` {_f(h.get('mean'))} on n = "
             f"{h.get('n_holdout_positions')} positions "
             f"(reads before adjudication: {h['reads_before_decision']}) — {h['note']}")
    L.append(f"- **arm builder**: {v['arm_builder']} · champion k_dets "
             f"{v['champion_k_dets']} x sims_per_det {v['champion_sims_per_det']} · "
             f"tiearb {v['champion']} · rules {v['rules_profiles']} · "
             f"band {v['band']} / corpus {v['corpus']}")
    L.append("")
    L.append("## §3 — the gates (FAIL-CLOSED; ABSENT IS FAIL)")
    L.append("")
    L.append("| gate | verdict | address that resolved | realized |")
    L.append("|---|---|---|---|")
    for g in v["gates"] + [v["witness_gate"]]:
        L.append(f"| `{g['id']}` | {'PASS ✅' if g['ok'] else 'FAIL ⛔'} | "
                 f"{g['address']} | `{json.dumps(g['realized'], default=str)[:400]}` |")
    L.append("")
    L.append("## §4.3 B — the honesty rails, all nine, on every branch")
    L.append("")
    for i, r in enumerate(v["honesty_rails"], 1):
        L.append(f"{i}. **{r['title']}.** {r['text']}")
    L.append("")
    L.append(f"**{v['scope_fence']}**")
    L.append("")
    L.append(f"**{v['size1_limits']}**")
    L.append("")
    L.append(f"**{v['truncation']['note']}** Chunks seen: {v['truncation']['chunks_seen']}.")
    L.append("")
    L.append("## §5 — what no branch does")
    L.append("")
    L.append(v["governance"])
    L.append("")
    L.append("No branch flips `governance/PRODUCTION.yaml`. No branch licenses a leaf, "
             "search, `B`, `M`, `--oracle-sims` or arbiter change. No branch re-rates the "
             "champion. No branch licenses an on-device or desktop DEPLOY. No branch "
             "authorizes SIZE-2 or SIZE-3 — a top-up is a FRESH OWNER FUNDING DECISION, "
             "re-priced by the measured `q`. No branch licenses a game cell; `E-CLEAN` at "
             "most licenses a DESIGN for one, and `E-CLEAN` CANNOT FIRE AT SIZE-1.")
    return "\n".join(L) + "\n"


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arb-records", action="append", default=[], required=False)
    ap.add_argument("--if-records", action="append", default=[], required=False)
    ap.add_argument("--plan-dir", required=True,
                    help="the PAIR dir (FRAME.json / PLAN_SUMMARY.json / SELECTION.jsonl)")
    ap.add_argument("--selection", default=None)
    ap.add_argument("--holdout-games", default=None)
    ap.add_argument("--knowngood", default=None,
                    help="path the KNOWNGOOD.json is READ from (the gate still RUNS the "
                         "probe_pickers.py knowngood subcommand first)")
    ap.add_argument("--knowngood-dir", default=None)
    ap.add_argument("--knowngood-if-records", default=None,
                    help="EP-D5: role-resolved ($SHARE) root threaded into the internal "
                         "'probe_pickers.py knowngood' re-invocation's --if-records, so it "
                         "does not fall back to probe_pickers.py's local-box hardcoded "
                         "DEFAULT_IF_RECORDS (the EP-D4 bug class, second call site)")
    ap.add_argument("--knowngood-arb-records", action="append", default=None,
                    help="EP-D5: same, for the re-invocation's (repeatable) --arb-records; "
                         "absent falls back to analyze_tiearb.DEFAULT_ARB_ROOTS")
    ap.add_argument("--python-exe", default=None)
    ap.add_argument("--blind-commit", default=None)
    ap.add_argument("--boot-seed", type=int, default=20260823)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--positions-dir", action="append", default=[])
    ap.add_argument("--if-positions-dir", action="append", default=[])
    ap.add_argument("--positions-glob", default="positions_chunk*")
    ap.add_argument("--if-positions-glob", default="positions_if_chunk*")
    ap.add_argument("--parity-base", type=int, default=PARITY_BASE)
    ap.add_argument("--n-priced-planned", type=int, default=N_PRICED_PLANNED)
    ap.add_argument("--kill-only", dest="kill_only", action="store_true", default=True,
                    help="READ_RULE §0.A (DEFAULT, and the funded size's own declaration)")
    a = ap.parse_args(argv)
    if not a.arb_records or not a.if_records:
        raise SystemExit("REFUSING: --arb-records and --if-records are both required")
    if a.blind_commit is None:
        a.blind_commit = str(Path(a.plan_dir) / "BLIND_COMMIT")
    return a


def main(argv=None) -> int:
    a = parse_args(argv)
    verdict, rows = build_readout(a)
    out = Path(a.out_dir)
    (out / "READOUT.json").write_text(json.dumps(verdict, indent=1, sort_keys=True,
                                                 default=str))
    (out / "READOUT.md").write_text(render(verdict))
    with open(out / "per_position.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")
    print(render(verdict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
