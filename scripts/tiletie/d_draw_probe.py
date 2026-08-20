#!/usr/bin/env python3
"""W9 / `D-DRAW` — the dedupe-partition probe for rung-3 `R5`.

Licensed by `rung3_r5/DESIGN.md` §"THE THREE GATE FAILURES" FIX 2 (2026-08-20)
and `READ_RULE.md` §2 `G-DDRAW` / §5 rider `I7`. Writes `RUN/D_DRAW.json`.

⛔ **`D-DRAW` ADJUDICATES NOTHING.** It moves no branch and may NEVER be used to
correct, reweight or re-scale `Δ_ora` (§0.D). That prohibition covers the Tier-1
fields added here exactly as it covers the chartered ones.

⚠️ **WHY THIS TOOL HAS TWO TIERS, AND WHY THE DISCHARGE RESTS ON TIER 1.**
`I7`(b)'s load-bearing conjunct is that the **python afterstate-dedupe key and
rust `string_representation` induce the SAME PARTITION of the tie set**. §0.D
chartered `D-DRAW` as the *"agreement rate between the instrument's `J=4` draw
and the deployed rust draw"* — but those two draws are **different RNG streams
by construction**: python `random.Random(sha256("tiletie-cap"|rid|20260812))`
versus rust MT19937 `sha256("tiearb2-deploy-v1"|digest|ply|"cap")`. That is the
very fact for which **`G-CAP` was retired as fail-always**. A raw set-overlap
between them is a **hypergeometric coincidence statistic**, not a partition
measurement, and printed bare it would re-admit `G-CAP`'s error through the
rider door. So:

  TIER 1 — the DIRECT comparison. Exact, and what `I7` actually asks. Both
           partitions are already materialized: the probe returns `tie_actions`
           and `n_distinct_afterstates`; `ARMS_R5.json` carries `arms_full`,
           `dedupe_dropped_actions` and `n_distinct_afterstates`. **The
           discharge cites this.**
  TIER 2 — the CHARTERED fields, kept verbatim because the pair names them in
           §6 and this tool may not remove them, emitted BESIDE their null model
           and labelled NOT-EVIDENCE-ABOUT-THE-PARTITION.

⚠️ **TIER 1 IS A NECESSARY-CONDITION WITNESS, NOT A PROOF.** Equal support plus
equal cell count is necessary for identical partitions and is **not sufficient**
— neither side exposes its grouping map. The read-out must state that limit and
must not round it up to "verified".

⛔ **THE POPULATION TRAP, closed by construction.** `ARMS_R5.json` carries BOTH
`capped` (false on all 1,060) and `capped_at_4` (true on all 1,060). The charter
says *"each S2 capped ply"*, so a builder filtering on the field whose NAME
matches the charter's word gets an **empty population, `n_checked == 0`, and a
vacuously-passing `G-DDRAW`**. **This tool applies NO FILTER**: the population is
every rid in `ARMS_R5.json`, and there is no flag that can narrow it. Both counts
are emitted so the artifact shows why.

⭐ **THE POSITION WITNESS IS MANDATORY.** A disagreement measured at the wrong
ply is worse than no measurement, so a rid whose replayed position does not
match `ARMS_R5`'s record is counted `n_unreconstructible` and **never compared**.
DESIGN asks for a stronger both-sides witness if one exists: it does. `n_legal`
AND `seat` are emitted by BOTH sides — `tiearb_probe` returns them (verified
against the rust emitter at call time) and `ARMS_R5` records `n_legal`/`seat`
(verified against `build_positions.build_arms_index`). Recorded as
`position_witness`, per READ_RULE §2.2's rule that an address is verified
against its own emitter before it is used.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

TOOL = "[d-draw]"

#: §R5-FINAL's pre-registered constants. The DEPLOYED draw's salt — NOT the
#: instrument cap draw's `tiletie-cap|<rid>|20260812`, which is the other stream
#: and the whole reason Tier 2 is not evidence.
DEPLOY_SALT = "tiearb2-deploy-v1"
DEPLOYED_CAP_J = 4
#: The pinned population size (§R5-FINAL.c). Not a filter — a SELF-CHECK.
N_POPULATION = 1060

REPO = Path(__file__).resolve().parents[2]
CAMPAIGN = REPO / "measurement" / "tiearb_widening_20260817" / "rung3_r5"
SCHEMA = "carcassonne-tiletie-d-draw/v1"


# --------------------------------------------------------------------------- #
# provenance — the D5 discipline, applied to the INSTRUMENT                     #
# --------------------------------------------------------------------------- #
def _licence_revs() -> dict:
    """The R5 two-rev licence, READ from the code-resident enumeration in
    `merge_legs` — never retyped here. One authority, one spelling."""
    sys.path.insert(0, str(REPO / "measurement" / "tiearb_widening_20260817"))
    import merge_legs as ML                                    # noqa: PLC0415
    return dict(ML.LICENSED_TRANCHE_REVS_R5)


def _rev_fragment_licensed(fragment: str, revs: dict):
    """The tranche a 12-char `carc_rs_build` fragment belongs to, or None.

    ⚠️ FIXED 12-CHAR WIDTH, never `core.abbrev`: the abbreviation width is a
    per-box git setting (measured on this very run — chunks 6-8 carry one commit
    as both `9bc2ab77` and `9bc2ab772`). One side of the comparison is always
    the enumerated 40-char sha; two abbreviations are never compared.
    """
    frag = str(fragment or "").lower()
    if len(frag) < 12:
        return None
    for name, sha in revs.items():
        if sha.lower().startswith(frag):
            return name
    return None


def provenance(revs: dict) -> dict:
    """`carc_rs_build` + `carc_rs_binary_sha` + the repo HEAD.

    ⛔ **THE LICENCE BAR BINDS THE INSTRUMENT, AND HERE IS WHY IT CANNOT BIND
    THIS FILE'S REV.** DESIGN FIX 2 requires the recorded rev to lie in the R5
    two-rev licence. Applied to the repo HEAD of the *analysis* code that bar is
    **fail-always by construction**: this probe is new code, it exists at
    NEITHER licensed rev, and any checkout that contains it necessarily has a
    HEAD outside the pair. A bar no healthy run can satisfy is the exact disease
    this campaign keeps killing (`G-CAP`, `G-TOOL`, `G-COLLIDE`, `G-SATURATION`).

    So the RAISE binds `carc_rs_build` — **the instrument the probe replays
    with, which is what the measurement actually depends on and what the scoring
    legs recorded**. The repo HEAD is RECORDED with its licence status and a
    note; it does not raise. ⚠️ REPORTED, not resolved silently: if the owner
    wants the literal reading, it is one line — and it will refuse every run.
    """
    from carcassonne_ai.rust_agent import (carc_rs_binary_sha,   # noqa: PLC0415
                                           carc_rs_build_id)
    build = carc_rs_build_id()
    frag = build.split("+")[1] if "+" in build else ""
    tranche = _rev_fragment_licensed(frag, revs)
    head = ""
    try:
        r = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        head = r.stdout.strip() if r.returncode == 0 else ""
    except OSError:
        head = ""
    return {
        "carc_rs_build": build,
        "carc_rs_binary_sha": carc_rs_binary_sha(),
        "instrument_rev_fragment": frag,
        "instrument_tranche": tranche,
        "instrument_rev_licensed": tranche is not None,
        "git_rev": head,
        "git_rev_licensed": any(s.lower().startswith(head.lower()[:12])
                                for s in revs.values()) if head else False,
        "licensed_revs": {k: v for k, v in sorted(revs.items())},
        "note": "the RAISE binds carc_rs_build (the instrument). git_rev is "
                "RECORDED, not gated: this probe is post-scoring code and "
                "exists at neither licensed rev, so gating it would refuse "
                "every healthy run (DEVIATIONS D6.1 — late, not contaminated). "
                "⚠️ carc_rs_binary_sha is BOX-LOCAL and is never compared "
                "across hosts (JCZ §0.F.2c).",
    }


# --------------------------------------------------------------------------- #
# inputs                                                                        #
# --------------------------------------------------------------------------- #
def load_arms(path) -> dict:
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise SystemExit(f"{TOOL} REFUSING: {path} is not a rid→meta object")
    return doc


def load_replay_rows(paths) -> dict:
    """rid → the pinned replay line (`deck_seed`, `ply`, `actions`).

    ⚠️ SOURCE, and a spec-vs-buildable note REPORTED rather than resolved:
    DESIGN FIX 2 spells the replay as *"replay the archived line (archive_path,
    deck_seed)"*, but **`archive_path` is `null` on all 1,060 rids of
    `ARMS_R5.json`** — measured, not assumed. The buildable equivalent is the
    STAGED LEG FILE, which carries `actions` + `deck_seed` + `ply` for every rid
    and is **sha-pinned by `G-CORPUS`** (`leg_sha256`). It is the same line from
    a pinned source; nothing is re-mined and no population changes.
    """
    out = {}
    for p in paths:
        p = Path(p)
        if not p.is_file():
            raise SystemExit(f"{TOOL} REFUSING: replay source {p} is ABSENT")
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            rid = row.get("rid")
            if rid and rid not in out:
                out[rid] = row
    return out


# --------------------------------------------------------------------------- #
# the per-rid comparison                                                        #
# --------------------------------------------------------------------------- #
def _replay(ms_factory, row, upto=None):
    ms = ms_factory(str(row["deck_seed"]))
    for a in row["actions"][:int(row["ply"]) if upto is None else upto]:
        ms.advance(int(a))
    return ms


def probe_rid(ms_factory, lc, meta: dict, row: dict) -> dict:
    """Replay to the recorded ply, then run BOTH tiers.

    `reconstructed=False` means the position witness failed and NOTHING was
    compared at this rid.
    """
    ply = int(row["ply"])
    ms = _replay(ms_factory, row)

    # ---- POSITION WITNESS — the STRONGEST both-sides field ---------------- #
    # ⭐ `checksum` is the python leg's recorded `MirrorState.string_repr()` and
    # is EXACTLY the witness `tier1_rust_leg` uses to gate its own root replay
    # (`rec["checksum_ok"]`) — verified against that emitter, per READ_RULE
    # §2.2. `n_legal`/`seat` are kept as secondary because they are cheap and
    # because a coincidence in one is not a coincidence in three.
    repr_ok = (row.get("checksum") is None
               or ms.string_repr() == row["checksum"])
    probe = ms.tiearb_probe(lc, -1, DEPLOYED_CAP_J, 0.0, DEPLOY_SALT, ply)
    legal_ok = probe.get("n_legal") == meta.get("n_legal")
    seat_ok = probe.get("seat") == meta.get("seat")
    witness_ok = bool(repr_ok and legal_ok and seat_ok)
    out = {"rid": row.get("rid"), "ply": ply, "reconstructed": witness_ok,
           "checksum_ok": bool(repr_ok), "n_legal_ok": bool(legal_ok),
           "seat_ok": bool(seat_ok), "fired": bool(probe.get("fired"))}
    if not witness_ok:
        out["why"] = ("position witness FAILED (checksum/n_legal/seat) — the "
                      "replayed position is not the recorded one, so nothing "
                      "was compared here")
        return out

    # ---- TIER 1 — THE PARTITION ITSELF (the discharge) -------------------- #
    # ⭐ This is `I7`(b) literally: does rust `string_representation` induce the
    # SAME PARTITION of the tie set as the python afterstate-dedupe key? The
    # python side materialized its partition as `arms_full` (one representative
    # per cell — `len(arms_full) == n_distinct_afterstates` on all 1,060) plus
    # `dedupe_dropped_actions` (the collapsed duplicates). So advance each tie
    # action from the SAME root, key the afterstate by `string_repr()`, and
    # compare the induced grouping directly.
    full = [int(x) for x in (meta.get("arms_full") or [])]
    dropped = [int(x) for x in (meta.get("dedupe_dropped_actions") or [])]
    keys = {}
    for a in full + dropped:
        after = _replay(ms_factory, row)
        after.advance(a)
        keys[a] = after.string_repr()
    kf = [keys[a] for a in full]
    kd = [keys[a] for a in dropped]
    reps_distinct = len(set(kf)) == len(kf)
    dropped_collapse = set(kd) <= set(kf)
    cells_equal = len(set(kf) | set(kd)) == meta.get("n_distinct_afterstates")
    out.update({
        "n_tie_actions": len(full) + len(dropped),
        "n_dropped": len(dropped),
        "reps_distinct": bool(reps_distinct),
        "dropped_collapse_onto_reps": bool(dropped_collapse),
        "cells_equal": bool(cells_equal),
        "partition_agree": bool(reps_distinct and dropped_collapse and cells_equal),
        # ⭐ THE STRENGTH OF THE PROOF IS PER-RID, not blanket. With NO dropped
        # actions the python partition is DISCRETE (every tie action its own
        # cell), so `reps_distinct` under the rust key proves the rust partition
        # is discrete too — the two partitions are then IDENTICAL, exactly.
        # Only where dedupe actually collapsed something is the check
        # necessary-condition-only: python does not record WHICH representative
        # each dropped action was collapsed onto, so equal counts plus
        # membership cannot pin the assignment.
        "exact_identity": bool(reps_distinct and dropped_collapse
                               and cells_equal and not dropped),
        "n_cells_rust": len(set(kf) | set(kd)),
        "n_cells_python": meta.get("n_distinct_afterstates"),
    })

    # ---- REPORTED, NOT A CONJUNCT: the two tie-set DEFINITIONS ------------ #
    # ⛔ DESIGN FIX 2 spelled Tier 1 as `set(probe.tie_actions) == set(arms_full)
    # | set(dedupe_dropped_actions)`. MEASURED: that is FALSE on ~57% of rids,
    # and NOT because the partitions disagree. The two sides enumerate DIFFERENT
    # OBJECTS: `tiearb_probe` returns the actions tied at the RUST ROOT LEAF
    # top-1, while the corpus's tie set is the champion's own tie set (carried
    # as `tie_size_exact` with its `gap`). Checked on rid
    # `tt_sp_135000000376_p24`: the six recorded arms hold TWO distinct leaf
    # values, so they cannot be a leaf-value tie set at all; the position itself
    # is confirmed correct by the checksum witness. Passing `champ_pick` does
    # not change it — the probe anchors on its own top-1 either way.
    # ⇒ The coincidence is REPORTED as what it is and is NOT part of the
    # discharge. Reporting it as a partition disagreement would have invented a
    # ~43% "agreement rate" out of a definitional mismatch.
    support_probe = set(int(x) for x in (probe.get("tie_actions") or []))
    support_py = set(full) | set(dropped)
    out.update({
        "probe_tieset_coincides": bool(support_probe == support_py),
        "n_support_probe": len(support_probe),
        "n_support_python": len(support_py),
    })

    # ---- TIER 2 — the CHARTERED draw overlap (NOT the discharge) ---------- #
    j4_arms = set(int(x) for x in (meta.get("subset_j4") or []))
    j4_probe = set(int(x) for x in (probe.get("arms") or []))
    overlap = len(j4_arms & j4_probe)
    out.update({
        "chartered_overlap": overlap,
        "chartered_agree": overlap == DEPLOYED_CAP_J
        and len(j4_arms) == DEPLOYED_CAP_J and len(j4_probe) == DEPLOYED_CAP_J,
        "n_j4_arms": len(j4_arms), "n_j4_probe": len(j4_probe),
        # ⚠️ the two draws do not even share a support unless the tie sets
        # coincide — one more reason the overlap is not evidence
        "chartered_same_support": bool(support_probe == support_py),
    })
    return out


def null_model(rows) -> dict:
    """The expected chartered overlap of two INDEPENDENT size-`J` draws from a
    shared support — the calibration without which Tier 2 is `G-CAP`'s error
    re-badged from a bar into a magnitude.

    For a support of size `T` and two independent uniform `J`-subsets:
      P(identical)      = 1 / C(T, J)
      E|intersection|   = J² / T
    ⚠️ `T <= J` forces identity — the comparison there CANNOT fail, so those
    rids are counted separately. On this corpus the arm counts run 5-13, so the
    count is expected to be 0; it is emitted anyway, because "expected 0" is not
    a measurement.
    """
    p_ident, e_overlap, forced = [], [], 0
    for r in rows:
        t, j = r.get("n_support_probe"), r.get("n_j4_probe")
        if not t or not j:
            continue
        if t <= j:
            forced += 1
            p_ident.append(1.0)
            e_overlap.append(float(j))
            continue
        p_ident.append(1.0 / math.comb(t, j))
        e_overlap.append(j * j / t)
    n = len(p_ident)
    return {
        "expected_identical_rate": (sum(p_ident) / n) if n else None,
        "expected_overlap": (sum(e_overlap) / n) if n else None,
        "n_forced_identical": forced,
        "basis": "two INDEPENDENT uniform J-subsets of the same support: "
                 "P(identical) = 1/C(T,J), E|intersection| = J^2/T",
        "label": "NOT-EVIDENCE-ABOUT-THE-PARTITION — the two draws are "
                 "different RNG streams BY CONSTRUCTION (python "
                 "random.Random(sha256('tiletie-cap'|rid|20260812)) vs rust "
                 "MT19937 sha256('tiearb2-deploy-v1'|digest|ply|'cap')), which "
                 "is why G-CAP was retired as fail-always. Read the Tier-1 "
                 "partition block for I7, never this.",
    }


# --------------------------------------------------------------------------- #
# the run                                                                       #
# --------------------------------------------------------------------------- #
def run(arms: dict, replay: dict, *, ms_factory=None, lc=None,
        prov: dict = None, expect_n: int = N_POPULATION) -> dict:
    """⛔ NO FILTER. Every rid in `arms` is in the population — see the module
    docstring's population trap."""
    if not arms:
        raise SystemExit(
            f"{TOOL} REFUSING: the population is EMPTY. `G-DDRAW` would pass "
            f"vacuously on n_checked == 0, which is the failure DESIGN FIX 2 "
            f"exists to close: ARMS_R5 carries `capped` (false on all 1,060) "
            f"beside `capped_at_4` (true on all 1,060), and a filter on the "
            f"field whose NAME matches the charter's word 'capped' empties the "
            f"population. This tool applies NO filter — an empty input means "
            f"the ARMS file is wrong, not that there is nothing to check.")

    rows, missing = [], []
    for rid in sorted(arms):
        row = replay.get(rid)
        if row is None:
            missing.append(rid)
            continue
        rows.append(probe_rid(ms_factory, lc, arms[rid], row))

    checked = [r for r in rows if r.get("reconstructed")]
    unrec = [r for r in rows if not r.get("reconstructed")]
    n_checked = len(checked)
    n_unrec = len(unrec) + len(missing)

    n_reps = sum(1 for r in checked if r["reps_distinct"])
    n_coll = sum(1 for r in checked if r["dropped_collapse_onto_reps"])
    n_cells = sum(1 for r in checked if r["cells_equal"])
    n_agree_p = sum(1 for r in checked if r["partition_agree"])
    n_agree_c = sum(1 for r in checked if r["chartered_agree"])
    n_with_dropped = sum(1 for r in checked if r["n_dropped"] > 0)
    n_dropped_total = sum(r["n_dropped"] for r in checked)
    n_coincide = sum(1 for r in checked if r["probe_tieset_coincides"])
    n_exact = sum(1 for r in checked if r["exact_identity"])
    n_necessary = n_agree_p - n_exact
    n_same_support = sum(1 for r in checked if r.get("chartered_same_support"))

    # ⭐ THE SELF-CHECK, so `G-DDRAW` cannot pass on a partial probe.
    d_draw_ran = bool(n_checked > 0 and (n_checked + n_unrec) == expect_n)

    doc = {
        "schema": SCHEMA,
        "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "marker": "[post-scoring]",
        "population": {
            "n_population": len(arms), "n_expected": expect_n,
            "filter": "NONE — every rid in ARMS_R5.json",
            "n_capped_true": sum(1 for m in arms.values() if m.get("capped") is True),
            "n_capped_at_4_true": sum(1 for m in arms.values()
                                      if m.get("capped_at_4") is True),
            "trap": "filtering on `capped` yields an EMPTY population and a "
                    "vacuously-passing G-DDRAW; `capped_at_4` is the field the "
                    "charter's word means. Neither is used as a filter here.",
        },
        "position_witness": {
            "fields": ["checksum", "n_legal", "seat"],
            "why": "`checksum` is the python leg's recorded "
                   "MirrorState.string_repr() and is the SAME witness "
                   "tier1_rust_leg uses to gate its own root replay — the "
                   "strongest both-sides field available, verified against that "
                   "emitter. `n_legal`/`seat` are emitted by BOTH sides "
                   "(tiearb_probe and build_positions.build_arms_index) and are "
                   "kept as secondary: a coincidence in one is not a "
                   "coincidence in three (READ_RULE §2.2). A partition "
                   "disagreement measured at the wrong ply is worse than no "
                   "measurement, so a witness failure is counted "
                   "n_unreconstructible and NOTHING is compared at that rid.",
        },
        # ---- TIER 1: THE DISCHARGE ---------------------------------------- #
        "partition": {
            "n_partition_checked": n_checked,
            "n_reps_distinct": n_reps,
            "n_dropped_collapse_onto_reps": n_coll,
            "n_cells_equal": n_cells,
            "n_partition_agree": n_agree_p,
            "partition_agreement_rate": (n_agree_p / n_checked) if n_checked else None,
            "n_rids_with_dropped": n_with_dropped,
            "n_dropped_actions": n_dropped_total,
            "is_the_discharge": True,
            "method": "each tie action is advanced from the SAME verified root "
                      "and its afterstate keyed by rust `string_repr()`; the "
                      "induced grouping is compared to the python partition "
                      "materialized as arms_full (one representative per cell) "
                      "+ dedupe_dropped_actions (the collapsed duplicates).",
            "conjuncts": "reps pairwise DISTINCT under the rust key AND every "
                         "dropped action collapses onto a representative AND "
                         "the rust cell count equals n_distinct_afterstates",
            "not_vacuous": "the collapse conjunct is carried by the rids with a "
                           "non-empty dedupe_dropped_actions — see "
                           "n_rids_with_dropped / n_dropped_actions. On a corpus "
                           "where dedupe dropped nothing it would be vacuous, "
                           "and that is why the count is printed.",
            # ⭐ THE STRENGTH IS SPLIT, not blanket (drafter 1c8daee7 amendment
            # 1). A single necessary-condition caveat over the whole population
            # UNDERSTATES the result: on a rid where dedupe dropped nothing the
            # python partition is DISCRETE, so pairwise-distinct rust keys prove
            # the partitions are identical outright.
            "n_exact_identity": n_exact,
            "n_necessary_condition": n_necessary,
            "n_necessary_condition_actions": n_dropped_total,
            "strength": (
                f"EXACT on {n_exact} rids; NECESSARY-CONDITION on "
                f"{n_necessary} ({n_dropped_total} actions)."),
            "why_the_split": "with NO dropped actions the python partition is "
                             "DISCRETE — every tie action its own cell — so "
                             "pairwise-distinct rust keys prove the rust "
                             "partition is discrete too, and the two are "
                             "IDENTICAL. Where dedupe DID collapse actions, "
                             "python does not record WHICH representative each "
                             "dropped action went to, so equal cell counts plus "
                             "membership are necessary and not sufficient.",
            "limit": "This compares the INDUCED GROUPING directly, which is "
                     "what I7(b) asks. It is still a witness about the tie sets "
                     "the corpus recorded — it says nothing about positions "
                     "outside them.",
        },
        "tieset_definition": {
            "n_probe_tieset_coincides": n_coincide,
            "rate": (n_coincide / n_checked) if n_checked else None,
            "is_the_discharge": False,
            "⛔": "REPORTED, NOT A CONJUNCT — and NOT a disagreement. DESIGN "
                 "FIX 2 spelled Tier 1 as `set(probe.tie_actions) == "
                 "set(arms_full) | set(dedupe_dropped_actions)`. MEASURED: the "
                 "two sides enumerate DIFFERENT OBJECTS — tiearb_probe returns "
                 "the actions tied at the RUST ROOT LEAF top-1, while the "
                 "corpus's tie set is the champion's own (carried as "
                 "tie_size_exact with its gap), and on rid "
                 "tt_sp_135000000376_p24 the six recorded arms hold TWO "
                 "distinct leaf values, so they are not a leaf-value tie set at "
                 "all. The position is confirmed by the checksum witness and "
                 "passing champ_pick does not change it. Scoring that formula "
                 "as the discharge would have invented a ~43% 'partition "
                 "disagreement' out of a definitional mismatch.",
        },
        # ---- TIER 2: THE CHARTERED FIELDS --------------------------------- #
        "n_checked": n_checked,
        "n_agree": n_agree_c,
        "agreement_rate": (n_agree_c / n_checked) if n_checked else None,
        # ⚠️ the chartered denominator is honest only with this beside it: where
        # the deployed trigger did not fire there is no rust draw at all, so
        # those rids can only ever count as DISagreement in a statistic that was
        # never measuring agreement in the first place
        "n_probe_fired": sum(1 for r in checked if r.get("fired")),
        "n_same_support": n_same_support,
        # ⭐ THE COMPARISON CURRENCY, pinned (drafter 1c8daee7 amendment 2).
        # `n_agree` counts EXACT MATCHES, so its only comparable null is
        # `expected_identical_rate` = mean 1/C(T,J). ⛔ NEVER compare it against
        # `expected_overlap`, which is a MEAN INTERSECTION SIZE — a different
        # quantity in different units. That two-currency slip is the same class
        # of error as grading a count against a fraction.
        "comparison": {
            "statistic": "n_agree / n_checked — the EXACT-MATCH rate",
            "comparable_null": "agreement_rate_null_model."
                               "expected_identical_rate  (mean 1/C(T,J))",
            "⛔ not_comparable": "agreement_rate_null_model.expected_overlap is "
                                "a MEAN INTERSECTION SIZE, not a rate. "
                                "Comparing an exact-match count against it is a "
                                "two-currency error.",
        },
        "agreement_rate_null_model": null_model(checked),
        # ⛔ THE INTERPRETATION, fixed in the artifact so no later reader has to
        # supply one. An exact-match rate BELOW its shared-support null is not a
        # finding: the null ASSUMES a shared support, and the supports coincide
        # on only `n_same_support` of `n_checked` rids. Where they differ the two
        # draws are selecting from different sets and an exact match is close to
        # impossible — which fully explains a sub-null reading.
        "interpretation": {
            "verdict": "CONFOUNDED AND UNINTERPRETABLE AS AN AGREEMENT MEASURE",
            "why": "the chartered comparison pits two draws from DIFFERENT RNG "
                   "streams and, on most rids, from different SUPPORTS "
                   "(chartered_same_support). Its shared-support null therefore "
                   "does not apply, and a reading below that null is fully "
                   "explained by the support mismatch.",
            "⛔ explicitly_not": "NOT evidence of disagreement between the two "
                                "draws, and NOT evidence about the partition. "
                                "The partition question is answered by the "
                                "`partition` block and nowhere else.",
        },
        "n_unreconstructible": n_unrec,
        "unreconstructible_detail": (
            [{"rid": r["rid"], "why": r.get("why")} for r in unrec[:20]]
            + [{"rid": rid, "why": "no replay line in the pinned leg file"}
               for rid in missing[:20]]),
        "d_draw_ran": d_draw_ran,
        "self_check": {
            "rule": "d_draw_ran := n_checked > 0 AND "
                    "n_checked + n_unreconstructible == n_expected",
            "n_checked": n_checked, "n_unreconstructible": n_unrec,
            "n_expected": expect_n,
        },
        "adjudicates": "NOTHING. D-DRAW moves no branch and may NEVER be used "
                       "to correct, reweight or re-scale Delta_ora (§0.D). The "
                       "prohibition covers the Tier-1 fields exactly as it "
                       "covers the chartered ones.",
    }
    if prov is not None:
        doc["provenance"] = prov
        doc["git_rev"] = prov.get("git_rev")
    return doc


def build_arg_parser():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--arms", default=str(CAMPAIGN / "ARMS_R5.json"),
                    help="the POPULATION AUTHORITY. Every rid in it is checked; "
                         "there is no filter flag, by design.")
    ap.add_argument("--leg", action="append", default=None,
                    help="pinned replay source(s) carrying actions+deck_seed+ply "
                         "(default: the staged positions_walled_leg1.jsonl)")
    ap.add_argument("--out", default=str(CAMPAIGN / "D_DRAW.json"))
    ap.add_argument("--expect-n", type=int, default=N_POPULATION,
                    help="the pinned population size the self-check requires")
    ap.add_argument("--dry-run", action="store_true",
                    help="compute and print; write nothing")
    return ap


def main(argv=None) -> int:
    a = build_arg_parser().parse_args(argv)
    legs = a.leg or [str(CAMPAIGN / "corpus" / "positions_s2"
                         / "positions_walled_leg1.jsonl")]
    revs = _licence_revs()
    prov = provenance(revs)

    # ⛔ THE PROVENANCE RAISE — before any measurement, so an unlicensed
    # instrument never produces a number someone could cite.
    if not prov["instrument_rev_licensed"]:
        print(f"{TOOL} ⛔ RAISE TO THE OWNER: carc_rs_build "
              f"{prov['carc_rs_build']!r} carries rev fragment "
              f"{prov['instrument_rev_fragment']!r}, which is NOT in the R5 "
              f"two-rev licence {sorted(revs.values())}. The wheel is not the "
              f"one this run scored with. Do NOT proceed and do NOT re-pin: "
              f"escalate.", file=sys.stderr)
        return 3

    import carc_rs                                              # noqa: PLC0415
    from carcassonne_ai.rust_agent import leaf_config_rs        # noqa: PLC0415
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG  # noqa: PLC0415
    lc = leaf_config_rs(DEFAULT_CONFIG)

    doc = run(load_arms(a.arms), load_replay_rows(legs),
              ms_factory=carc_rs.MirrorState.from_seed, lc=lc, prov=prov,
              expect_n=a.expect_n)

    p = doc["partition"]
    print(f"{TOOL} population {doc['population']['n_population']} | "
          f"checked {doc['n_checked']} | unreconstructible "
          f"{doc['n_unreconstructible']} | d_draw_ran={doc['d_draw_ran']}")
    print(f"{TOOL} TIER 1 (the discharge): partition_agree "
          f"{p['n_partition_agree']}/{p['n_partition_checked']} "
          f"(reps distinct {p['n_reps_distinct']}, dropped collapse "
          f"{p['n_dropped_collapse_onto_reps']}, cells {p['n_cells_equal']})")
    print(f"{TOOL}   strength: {p['strength']}")
    td = doc["tieset_definition"]
    print(f"{TOOL} tie-set DEFINITION coincidence (reported, NOT the "
          f"discharge): {td['n_probe_tieset_coincides']}/{doc['n_checked']}")
    print(f"{TOOL} TIER 2 (chartered, NOT the discharge): exact matches "
          f"{doc['n_agree']}/{doc['n_checked']} vs the ONLY comparable null "
          f"(expected_identical_rate) "
          f"{doc['agreement_rate_null_model']['expected_identical_rate']} — "
          f"same support on {doc['n_same_support']}/{doc['n_checked']}")
    print(f"{TOOL}   {doc['interpretation']['verdict']} — not evidence of "
          f"disagreement, and not evidence about the partition")
    if not a.dry_run:
        Path(a.out).write_text(json.dumps(doc, indent=2, sort_keys=True))
        print(f"{TOOL} -> {a.out}")
    return 0 if doc["d_draw_ran"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
