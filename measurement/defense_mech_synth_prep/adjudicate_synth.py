#!/usr/bin/env python3
"""SYNTH-MECH — THE ADJUDICATOR (aggregate + gates + the READ_RULE executor).

Two jobs, in this order and never the other way round:

  1. **THE GATES** (PREREG.md §6). Every gate below must PASS or the read is
     `SYNTH-VOID-INSTRUMENT`. `ABSENT` is `FAIL` at every one of them — never a
     skip, never a default — and each gate row names the DOCUMENT+FIELD that
     answered it. A void is not a null and may never be quoted as one.
  2. **THE READ RULE** (PREREG.md §7). ONE confirmatory leg — the PRIMARY —
     two-sided alpha 0.05, `|z| >= 1.9600` on its own REALIZED cluster-robust
     se, then the frozen branch map. `BAR_CLAUSE = +1.75 pts/ply`.
     Where this file and PREREG.md disagree, PREREG wins and this file is the
     defect.

⛔ SCOPE. This instrument prices **the CLAUSE** — CL-083's amended claim that a
champion-continuation future prices defense/steering divergences ~0 *because
the continuation estimand is policy-conditional*. It says nothing about the
owner's edge, no owner ply is in it, and a result here never substitutes for
`measurement/defense_primary_prep/`.

THE ESTIMATOR (PREREG §3). A ply's price PER FAMILY is the mean of its landed
CRN worlds' `delta_pts_mover[family]`; a ply's FAMILY DELTA is the mean of
`delta[armed] - delta[champ]` over the SAME landed world set. A stratum's
family delta is the unweighted mean over its plies, cluster-robust SE
clustered on GAME (`deck_seed`) via influence functions. The PRIMARY is
`family_delta(defense) - family_delta(control)`, whose SE is built from
per-game influence contributions of the DIFFERENCE so a game shared by both
strata is a paired, not an independent, observation.

⚠️ MOST GATES HERE RE-DERIVE FROM THE RAW ROWS RATHER THAN TRUSTING A STORED
LABEL — in particular `G-WITNESS` re-derives every arm's witness from
`jr_expansions` rather than trusting the stored `family_witness` field, and
`G-ROOT` re-derives root identity from `arms[*].witness` rather than trusting
`pair.root_identity_ok`. This is a DELIBERATE departure from E-1b's adjudicator
(which trusted the stored witness) — see PREREG §6's gate table.

No judged quantity appears anywhere: every number here is a difference of
REALIZED final scores.
"""
from __future__ import annotations

import argparse
import collections
import copy
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path

DIR = Path(__file__).resolve().parent

SCHEMA_UNIT = "defense-mech-synth/v1/unit"
SCHEMA_MANIFEST = "defense-mech-synth/v1"
SCHEMA_SELECTION = "defense-mech-synth/v1/selection"
SCHEMA_VERDICT = "defense-mech-synth-verdict/v1"

# --------------------------------------------------------------------------- #
# ⛔ FROZEN CONSTANTS — hard-coded independently of synth_mech.py, on purpose:  #
# the point of this gate suite is an INDEPENDENT assertion, not a config echo. #
# Sourced from PREREG.md §1.1. If PREREG changes these, this file is stale.    #
# --------------------------------------------------------------------------- #
WORLD_SEED = 20260902
CONTINUATION_SEED = 0
M_WORLDS = 8
ARM_DOSE = 0.25
ARM_MASK = 31
ARM_SCOPE = "opp"
PINNED_K_DETS = 8
PINNED_SIMS_PER_DET = 1376
PINNED_EXACT_K = 2
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"
RULES_PROFILE = "fixed_v1"

FAMILIES = ("champ", "armed")
PICKS = ("pick_champ", "pick_armed")
ARMS = tuple(f"{p}__{f}" for f in FAMILIES for p in PICKS)
JR_KEYS = ("total", "own_mover", "boosted")
CRN_WITNESS_KEYS = ("root_repr_sha", "world_deck_sha", "world_deck_len",
                    "n_drawn_prefix", "n_legal_root", "move_idx_at_root")
DET_SEED_KEY = "det_seed_base_at_root"

# --- the bar + read-rule constants (PREREG §4, §7) --------------------------- #
BAR_CLAUSE = 1.75
Z_CRIT = 1.9600
SE_MODEL = 0.800
SE_RATIO_LOW, SE_RATIO_HIGH = 0.70, 1.43
N_FLOOR = 160
LANDING_RATE_FLOOR = 0.95
SMD_MAX = 0.25
VOID_RATE_MAX = 0.10
CORRECTNESS_VOID_REASONS = {"root_identity_mismatch", "arm_witness_failed",
                            "arms_missing"}
COVERAGE_ADVISORY_FLOOR = 0.5

# --- PREREG §9, copied verbatim so the verdict document carries its own       #
#     guardrails ------------------------------------------------------------- #
FORBIDDEN_READINGS = [
    "|z| < 2 is never \"refuted.\" Killed / dead / does nothing are forbidden "
    "readings of a bounded null. Quote the bound.",
    "A void is not a null (IS-A1). It may never be quoted as one.",
    "No number in this round may be contrasted with E-1a's or E-1b's as a "
    "statistic. Different games, a different WORLD_SEED, a different "
    "selector, a different corpus. Any such comparison is context, and must "
    "be labelled so.",
    "The raw family delta of a single stratum is NOT the clause. It is "
    "positive by construction (§2.3). Quoting family_delta(defense) without "
    "family_delta(control) beside it is a forbidden reading of this round.",
    "Nothing here licenses a PRODUCTION.yaml change, an S1 re-opening, a "
    "results.csv elo row, or any statement about Joshua's play.",
    "Do not re-read these plies under a moved bar. A later argument that the "
    "bar was mis-set is a new prereg on fresh plies, not a re-read.",
    "The censuses are not comparable across strata as a mechanism claim. "
    "They count expansions, not exploits.",
    "A stratum price larger than the threatened feature's own points is a "
    "bug signal, not a discovery.",
    "CLAUSE-GENERALITY-REFUTED does not refute the E-1b observation. It says "
    "the mechanism did not reproduce on a synthetic corpus. Those are "
    "different sentences and only the second one is licensed.",
]


# --------------------------------------------------------------------------- #
# small utilities                                                              #
# --------------------------------------------------------------------------- #
def sha256_file(path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _flat(obj, prefix=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _flat(v, f"{prefix}.{k}" if prefix else str(k))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            yield from _flat(v, f"{prefix}[{i}]")
    else:
        yield prefix, obj


def _uid(u: dict) -> str:
    return f"{u.get('deck_seed')}_p{u.get('ply')}_w{u.get('world')}"


def _g(name, ok, address, says, note="") -> dict:
    return {"gate": name, "status": "PASS" if ok else "FAIL",
            "address": address, "says": says, "note": note}


# --------------------------------------------------------------------------- #
# THE WITNESSES — re-derived from jr_expansions, NEVER from the stored         #
# family_witness field (PREREG §6 G-WITNESS: "do NOT trust the stored...")     #
# --------------------------------------------------------------------------- #
def scope_witness(census, scope: str = ARM_SCOPE) -> dict:
    """The five hard checks for an ARMED-family arm (PREREG §2.5)."""
    if not isinstance(census, dict):
        return {"ok": False, "failures": ["census_absent_stale_wheel"],
                "coverage": None, "denominator": None}
    missing = [k for k in JR_KEYS if k not in census]
    if missing:
        return {"ok": False, "failures": [f"census_missing_keys:{missing}"],
                "coverage": None, "denominator": None}
    try:
        total, own = int(census["total"]), int(census["own_mover"])
        boosted = int(census["boosted"])
    except (TypeError, ValueError):
        return {"ok": False, "failures": ["census_not_integers"],
                "coverage": None, "denominator": None}
    fail = []
    if total <= 0:
        fail.append("total_not_positive")
    if not (0 <= own <= max(total, 0)):
        fail.append("own_mover_out_of_range")
    if boosted <= 0:
        fail.append("boosted_not_positive__knob_never_expressed")
    if scope == "own":
        den = own
    elif scope == "opp":
        den = total - own
    else:
        den = total
    if boosted > max(den, 0):
        fail.append(f"boosted_outside_scope:{boosted}>{den}")
    return {"ok": not fail, "failures": fail, "denominator": den,
            "coverage": (boosted / den) if den > 0 else None}


def champ_witness(census) -> dict:
    """The CHAMPION-family arm's witness — census must be EXACTLY all-zero."""
    if not isinstance(census, dict):
        return {"ok": False, "failures": ["census_absent_stale_wheel"]}
    missing = [k for k in JR_KEYS if k not in census]
    if missing:
        return {"ok": False, "failures": [f"census_missing_keys:{missing}"]}
    try:
        vals = {k: int(census[k]) for k in JR_KEYS}
    except (TypeError, ValueError):
        return {"ok": False, "failures": ["census_not_integers"]}
    bad = [k for k, v in vals.items() if v != 0]
    return {"ok": not bad,
            "failures": [f"dose0_census_nonzero:{bad}"] if bad else []}


# --------------------------------------------------------------------------- #
# LOADING                                                                      #
# --------------------------------------------------------------------------- #
def load_units(units_dir) -> list[dict]:
    return [json.loads(p.read_text())
            for p in sorted(Path(units_dir).glob("unit_*.json"))]


def load_targets(targets_path) -> list[dict]:
    return [json.loads(l) for l in Path(targets_path).read_text().splitlines()
            if l.strip()]


def load_json_or_none(path):
    p = Path(path) if path else None
    if p is None or not p.exists():
        return None
    return json.loads(p.read_text())


# --------------------------------------------------------------------------- #
# THE ESTIMATOR (PREREG §3)                                                    #
# --------------------------------------------------------------------------- #
def collapse_worlds(units: list[dict]) -> list[dict]:
    """(deck_seed, ply) -> one priced ply: the mean over its LANDED CRN worlds."""
    by = collections.OrderedDict()
    for u in units:
        by.setdefault((int(u["deck_seed"]), int(u["ply"])), []).append(u)
    out = []
    for (seed, ply), us in by.items():
        ok = [u for u in us if (u.get("pair") or {}).get("status") == "OK"]
        void = [u for u in us if (u.get("pair") or {}).get("status") != "OK"]
        h = us[0]
        price_champ = [u["pair"]["delta_pts_mover"]["champ"] for u in ok]
        price_armed = [u["pair"]["delta_pts_mover"]["armed"] for u in ok]
        fam_delta = [u["pair"]["family_delta"] for u in ok]
        out.append({
            "deck_seed": seed, "ply": ply, "stratum": h.get("stratum"),
            "mover": h.get("mover"), "n_plies": h.get("n_plies"),
            "m_worlds_ok": len(ok), "m_worlds_void": len(void),
            "void_reasons": sorted({(u.get("pair") or {}).get("reason")
                                    for u in void} - {None}),
            "price_champ": statistics.fmean(price_champ) if price_champ else None,
            "price_armed": statistics.fmean(price_armed) if price_armed else None,
            "family_delta": statistics.fmean(fam_delta) if fam_delta else None,
            "worlds_ok": sorted(int(u["world"]) for u in ok),
        })
    return out


def _influence(plies, sign=1.0, field="family_delta"):
    n = len(plies)
    if n == 0:
        return {}, 0.0
    mu = statistics.fmean(p[field] for p in plies)
    contrib = collections.defaultdict(float)
    for p in plies:
        contrib[p["deck_seed"]] += sign * (p[field] - mu) / n
    return dict(contrib), mu


def cluster_stats(plies, field="family_delta") -> dict:
    """Mean + cluster-robust SE, clustered on GAME (`deck_seed`)."""
    plies = [p for p in plies if p.get(field) is not None]
    n = len(plies)
    if n == 0:
        return {"n": 0, "n_clusters": 0, "mean": None, "se": None, "z": None,
                "ci95_low": None, "ci95_high": None}
    contrib, mu = _influence(plies, field=field)
    g = len(contrib)
    var = sum(v * v for v in contrib.values())
    if g > 1:
        var *= g / (g - 1.0)
    se = math.sqrt(var)
    z = (mu / se) if se > 0 else None
    return {"n": n, "n_clusters": g, "mean": mu, "se": se, "z": z,
            "ci95_low": (mu - Z_CRIT * se) if se is not None else None,
            "ci95_high": (mu + Z_CRIT * se) if se is not None else None}


def contrast(a, b, field="family_delta") -> dict:
    """`mean(a) - mean(b)` with a cluster-robust SE that SHARES game clusters
    (PREREG §3: "games can contribute to BOTH strata")."""
    a = [p for p in a if p.get(field) is not None]
    b = [p for p in b if p.get(field) is not None]
    if not a or not b:
        return {"n_a": len(a), "n_b": len(b), "diff": None, "se": None,
                "z": None, "ci95_low": None, "ci95_high": None,
                "n_clusters": 0, "n_shared_clusters": 0}
    ca, ma = _influence(a, 1.0, field)
    cb, mb = _influence(b, -1.0, field)
    keys = set(ca) | set(cb)
    var = sum((ca.get(k, 0.0) + cb.get(k, 0.0)) ** 2 for k in keys)
    g = len(keys)
    if g > 1:
        var *= g / (g - 1.0)
    se = math.sqrt(var)
    diff = ma - mb
    z = (diff / se) if se > 0 else None
    return {"n_a": len(a), "n_b": len(b), "mean_a": ma, "mean_b": mb,
            "diff": diff, "se": se, "z": z, "n_clusters": g,
            "n_shared_clusters": len(set(ca) & set(cb)),
            "ci95_low": (diff - Z_CRIT * se) if se is not None else None,
            "ci95_high": (diff + Z_CRIT * se) if se is not None else None}


def _corr(xs, ys):
    n = len(xs)
    if n < 2:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    sy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if sx == 0 or sy == 0:
        return None
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / (sx * sy)


def recon_primary(units: list[dict]):
    """RECON — the PRIMARY recomputed by a DELIBERATELY DIFFERENT code path:
    flat, sorted by (deck_seed, ply), `math.fsum`. It can only VOID a number,
    never move it."""
    per = collections.defaultdict(list)
    for u in sorted(units, key=lambda u: (u["deck_seed"], u["ply"], u["world"])):
        pair = u.get("pair") or {}
        if pair.get("status") != "OK":
            continue
        stratum = u.get("stratum")
        if stratum not in ("defense", "control"):
            continue
        fd = pair.get("family_delta")
        if fd is None:
            continue
        per[(stratum, u["deck_seed"], u["ply"])].append(float(fd))
    prices = {k: math.fsum(v) / len(v) for k, v in sorted(per.items())}
    d = [v for k, v in sorted(prices.items()) if k[0] == "defense"]
    c = [v for k, v in sorted(prices.items()) if k[0] == "control"]
    if not d or not c:
        return None
    return math.fsum(d) / len(d) - math.fsum(c) / len(c)


# --------------------------------------------------------------------------- #
# THE GATES (PREREG §6) — ABSENT is FAIL; each names the address that          #
# answered it                                                                  #
# --------------------------------------------------------------------------- #
def gate_manifest(manifest, man_path, targets_path) -> dict:
    if not manifest:
        return _g("G-MANIFEST", False, str(man_path), "ABSENT",
                  "no manifest.json — config may not be quoted from a dirname")
    bad = []
    if manifest.get("schema") != SCHEMA_MANIFEST:
        bad.append(f"schema={manifest.get('schema')!r}")
    if int(manifest.get("world_seed", -1)) != WORLD_SEED:
        bad.append(f"world_seed={manifest.get('world_seed')!r}")
    if int(manifest.get("continuation_seed", -1)) != CONTINUATION_SEED:
        bad.append(f"continuation_seed={manifest.get('continuation_seed')!r}")
    if int(manifest.get("m_worlds", -1)) != M_WORLDS:
        bad.append(f"m_worlds={manifest.get('m_worlds')!r}")
    a = manifest.get("arming") or {}
    if (abs(float(a.get("dose", -1)) - ARM_DOSE) > 1e-12
            or int(a.get("mask", -1)) != ARM_MASK
            or str(a.get("scope")) != ARM_SCOPE):
        bad.append(f"arming={a}")
    b = manifest.get("budget_pin") or {}
    if (int(b.get("k_dets", -1)) != PINNED_K_DETS
            or int(b.get("sims_per_det", -1)) != PINNED_SIMS_PER_DET
            or int(b.get("exact_max_k", -1)) != PINNED_EXACT_K):
        bad.append(f"budget_pin={b}")
    if manifest.get("leaf_hash_of_record") != LEAF_HASH_OF_RECORD:
        bad.append(f"leaf_hash_of_record={manifest.get('leaf_hash_of_record')!r}")
    if manifest.get("rules_profile") != RULES_PROFILE:
        bad.append(f"rules_profile={manifest.get('rules_profile')!r}")
    want_sha = sha256_file(targets_path) if targets_path else None
    if want_sha is None or manifest.get("targets_sha256") != want_sha:
        bad.append(f"targets_sha256 manifest={manifest.get('targets_sha256')!r} "
                   f"file={want_sha!r}")
    return _g("G-MANIFEST", not bad,
              f"{man_path}::schema,world_seed,arming,budget_pin,"
              f"leaf_hash_of_record,rules_profile,targets_sha256",
              "frozen fields match the independent constants this adjudicator "
              "is written against" if not bad else f"MISMATCH {bad}")


def gate_leaf(manifest, man_path) -> dict:
    """⭐ INVERTED: the recorded leaf hash EQUALS the hash of record. Surface B
    moves no leaf hash, so a MOVED hash is never this round's doing."""
    if not manifest:
        return _g("G-LEAF", False, str(man_path), "ABSENT manifest")
    if manifest.get("leaf_hash_of_record") != LEAF_HASH_OF_RECORD:
        return _g("G-LEAF", False, f"{man_path}::leaf_hash_of_record",
                  f"leaf_hash_of_record={manifest.get('leaf_hash_of_record')!r} "
                  f"!= {LEAF_HASH_OF_RECORD!r}")
    lm = manifest.get("leaf_manifest") or {}
    hashes = sorted({str(v) for k, v in _flat(lm) if "hash" in str(k).lower()})
    ok = LEAF_HASH_OF_RECORD in hashes
    return _g("G-LEAF", ok, f"{man_path}::leaf_manifest",
              f"hashes={hashes}" if ok else
              f"MOVED: {LEAF_HASH_OF_RECORD} not among {hashes}")


def gate_negctrl(manifest, man_path) -> dict:
    """The pre-flight dose-0 census is all-zero and the dose-d* census has
    boosted > 0 — re-derived from the recorded censuses, not the stored `ok`."""
    nc = (manifest or {}).get("negative_control") or {}
    z = (nc.get("unarmed_dose0") or {}).get("census") or {}
    d = (nc.get("armed_dose_dstar") or {}).get("census") or {}
    z_ok = bool(z) and all(int(z.get(k, -1)) == 0 for k in JR_KEYS)
    d_ok = int(d.get("boosted", 0)) > 0
    ok = bool(nc.get("ok")) and z_ok and d_ok
    return _g("G-NEGCTRL", ok, f"{man_path}::negative_control",
              f"dose0={z} dose_dstar={d} stored_ok={nc.get('ok')}")


def gate_witness(units: list[dict]) -> dict:
    """⭐⭐ On EVERY landed arm: armed-family arms pass the five hard checks;
    champion-family arms have a census EXACTLY all-zero. Re-derived from
    `jr_expansions`, never from the stored `family_witness`."""
    bad, coverages, exact = [], [], 0
    n_armed = n_champ = 0
    for u in units:
        for name, arm in (u.get("arms") or {}).items():
            if arm.get("status") != "OK":
                continue
            fam = arm.get("family")
            census = arm.get("jr_expansions")
            if fam == "armed":
                n_armed += 1
                w = scope_witness(census, ARM_SCOPE)
                if not w["ok"]:
                    bad.append({"unit": _uid(u), "arm": name,
                               "failures": w["failures"], "census": census})
                if w.get("coverage") is not None:
                    coverages.append(w["coverage"])
                    if w.get("denominator") and census.get("boosted") == w["denominator"]:
                        exact += 1
            elif fam == "champ":
                n_champ += 1
                w = champ_witness(census)
                if not w["ok"]:
                    bad.append({"unit": _uid(u), "arm": name,
                               "failures": w["failures"], "census": census})
            else:
                bad.append({"unit": _uid(u), "arm": name,
                           "failures": [f"unknown_family:{fam}"]})
    mean_cov = statistics.fmean(coverages) if coverages else None
    ok = (not bad) and (n_armed + n_champ) > 0
    g = _g("G-WITNESS", ok, "units/*.json::arms[*].jr_expansions (re-derived)",
           f"{n_armed} armed + {n_champ} champ landed arms checked; "
           f"mean armed coverage {None if mean_cov is None else round(mean_cov, 4)}; "
           f"exact partition {exact}/{n_armed}"
           + ("" if not bad else f"; FAILURES {bad[:5]}"))
    g["advisory_low_coverage"] = bool(mean_cov is not None
                                      and mean_cov < COVERAGE_ADVISORY_FLOOR)
    g["mean_coverage"] = mean_cov
    g["n_armed_arms"] = n_armed
    g["n_champ_arms"] = n_champ
    return g


def gate_arming(units: list[dict]) -> dict:
    """The RESOLVED knobs on every landed arm, read off the rust side's own
    stats: armed -> dose 0.25 / mask 31 / scope opp; champ -> dose 0.0."""
    bad = []
    for u in units:
        for name, arm in (u.get("arms") or {}).items():
            if arm.get("status") != "OK":
                continue
            fam = arm.get("family")
            ar = arm.get("arming_resolved") or {}
            if fam == "armed":
                if (abs(float(ar.get("dose", -1)) - ARM_DOSE) > 1e-12
                        or int(ar.get("mask", -1)) != ARM_MASK
                        or str(ar.get("scope")) != ARM_SCOPE):
                    bad.append({"unit": _uid(u), "arm": name, "resolved": ar})
            elif fam == "champ":
                if abs(float(ar.get("dose", -1))) > 1e-12:
                    bad.append({"unit": _uid(u), "arm": name, "resolved": ar})
    return _g("G-ARMING", not bad, "units/*.json::arms[*].arming_resolved",
              f"dose {ARM_DOSE}/mask {ARM_MASK}/scope {ARM_SCOPE} on every armed "
              f"arm; dose 0.0 on every champ arm" if not bad
              else f"DRIFT {bad[:5]}")


def gate_budget(units: list[dict]) -> dict:
    """Every arm AND every selector row resolved k8x1376, exact-K 2. (Selector
    rows are not carried on the unit; this gate checks every landed ARM.)"""
    bad = []
    for u in units:
        for name, arm in (u.get("arms") or {}).items():
            if arm.get("status") != "OK":
                continue
            ar = arm.get("arming_resolved") or {}
            if (int(ar.get("k_dets", -1)) != PINNED_K_DETS
                    or int(ar.get("sims_per_det", -1)) != PINNED_SIMS_PER_DET
                    or int(ar.get("exact_max_k", -1)) != PINNED_EXACT_K):
                bad.append({"unit": _uid(u), "arm": name, "resolved": ar})
    return _g("G-BUDGET", not bad, "units/*.json::arms[*].arming_resolved",
              f"k{PINNED_K_DETS}x{PINNED_SIMS_PER_DET} exact-K{PINNED_EXACT_K} "
              f"on every landed arm" if not bad else f"DRIFT {bad[:5]}")


def gate_root(units: list[dict]) -> dict:
    """⭐ THE SINGLE-VARIABLE PROOF. Within every unit, all FOUR arms agree
    bit-for-bit on the six CRN witness fields (re-derived from `arms[*]
    .witness`, never `pair.root_identity_ok`); `det_seed_base_at_root` agrees
    WITHIN family only. A mismatch is a BUG SIGNAL, never attrition."""
    bad, checked = [], 0
    for u in units:
        arms = u.get("arms") or {}
        witnesses = {name: (arms.get(name) or {}).get("witness") for name in ARMS}
        if any(w is None for w in witnesses.values()):
            continue          # arms_missing / not-OK — covered by G-VOID
        ref = witnesses[ARMS[0]]
        mismatched = sorted({k for w in witnesses.values() for k in CRN_WITNESS_KEYS
                             if w.get(k) != ref.get(k)})
        det_bad = []
        for fam in FAMILIES:
            vals = {witnesses[f"{p}__{fam}"].get(DET_SEED_KEY) for p in PICKS}
            if len(vals) > 1:
                det_bad.append(fam)
        checked += 1
        if mismatched or det_bad:
            bad.append({"unit": _uid(u), "fields": mismatched,
                       "det_seed_families": det_bad})
    ok = (not bad) and checked > 0
    return _g("G-ROOT", ok, "units/*.json::arms[*].witness",
              f"{checked} units' 4 arms agree bit-for-bit on all 6 CRN fields; "
              f"det_seed_base agrees within family" if not bad
              else f"MISMATCH {bad[:5]}")


def gate_identity(units: list[dict]) -> dict:
    """Every identity-set unit prices EXACTLY 0.0 in BOTH families, and its two
    picks agree. Any nonzero is an RNG leak."""
    bad, n = [], 0
    for u in units:
        if u.get("stratum") != "identity":
            continue
        n += 1
        pair = u.get("pair") or {}
        if pair.get("status") != "OK":
            bad.append({"unit": _uid(u), "why": "pair.status != OK"})
            continue
        if u.get("pick_champ") != u.get("pick_armed"):
            bad.append({"unit": _uid(u), "why": "picks differ",
                       "pick_champ": u.get("pick_champ"),
                       "pick_armed": u.get("pick_armed")})
            continue
        d = pair.get("delta_pts_mover") or {}
        fd = pair.get("family_delta")
        if d.get("champ") != 0 or d.get("armed") != 0 or fd != 0:
            bad.append({"unit": _uid(u), "delta_pts_mover": d, "family_delta": fd})
    ok = (not bad) and n > 0
    return _g("G-IDENTITY", ok, "units/*.json (stratum==identity)"
             "::pick_champ,pick_armed,pair.delta_pts_mover,pair.family_delta",
              f"{n - len(bad)}/{n} identity units exactly zero in both families"
              if n else "ABSENT — no identity-stratum units found",
              "" if not bad else f"NONZERO/DIVERGENT {bad[:5]}")


def gate_select(units, targets, targets_path, manifest, selection,
               select_rows_dir=None) -> dict:
    """The priced set == the frozen target set exactly; both sha256 checks;
    and (if `--select-rows` is given) a byte-for-byte re-run of the frozen
    selector."""
    target_keys = {(int(t["deck_seed"]), int(t["ply"])) for t in targets}
    priced_keys = {(int(u["deck_seed"]), int(u["ply"])) for u in units}
    strays = sorted(priced_keys - target_keys)
    missing = sorted(target_keys - priced_keys)
    want_sha = sha256_file(targets_path) if targets_path else None
    man_sha_ok = manifest is not None and manifest.get("targets_sha256") == want_sha
    sel_sha_ok = selection is not None and selection.get("targets_sha256") == want_sha

    rerun_note = "SKIPPED-NO-SELECT-ROWS"
    rerun_ok = True
    if select_rows_dir:
        sys.path.insert(0, str(DIR))
        import synth_mech            # noqa: PLC0415  (deliberate: the FROZEN selector)
        rows = [json.loads(p.read_text())
                for p in sorted(Path(select_rows_dir).glob("s_*.json"))]
        built = synth_mech.build_targets(rows)
        got = "".join(json.dumps(r, sort_keys=True) + "\n" for r in built["targets"])
        want = Path(targets_path).read_text()
        rerun_ok = got == want
        rerun_note = "rerun matches byte-for-byte" if rerun_ok else "rerun MISMATCH"

    ok = (not strays) and (not missing) and man_sha_ok and sel_sha_ok and rerun_ok
    return _g("G-SELECT", ok,
              "units/*.json vs targets vs manifest.json vs SELECTION.json",
              f"priced=={len(priced_keys)} target=={len(target_keys)} "
              f"strays={strays[:3]} missing={missing[:3]} "
              f"manifest_sha_ok={man_sha_ok} selection_sha_ok={sel_sha_ok} "
              f"select_rows_rerun={rerun_note}")


def gate_match(selection, smoke: bool) -> dict:
    """|SMD| <= 0.25 on each MATCHED covariate. Relaxed to a PASS under
    --smoke (n=3/stratum cannot balance)."""
    if smoke:
        return _g("G-MATCH", True, "SELECTION.json::balance",
                  "RELAXED-SMOKE: n=3/stratum cannot balance; not gated under "
                  "--smoke")
    bal = (selection or {}).get("balance") or {}
    matched = {k: v for k, v in bal.items() if v.get("matched")}
    bad = [{"cov": k, "smd": v.get("smd")} for k, v in matched.items()
           if v.get("smd") is None or abs(v["smd"]) > SMD_MAX]
    ok = bool(matched) and not bad
    return _g("G-MATCH", ok, "SELECTION.json::balance",
              f"|SMD|<={SMD_MAX} on all {len(matched)} matched covariates"
              if ok else f"OUT OF BALANCE (or ABSENT) {bad or 'no matched block'}")


def gate_n(plies, units, targets, manifest, smoke: bool) -> dict:
    """n_defense >= 160 AND n_control >= 160 (relaxed under --smoke to '>=1
    unit priced overall'); every target ply in {defense,control} priced
    (ALWAYS hard, even under --smoke); >=95% of requested worlds landed
    (relaxed under --smoke)."""
    plies_by_key = {(p["deck_seed"], p["ply"]): p for p in plies}
    dc_targets = [t for t in targets if t.get("stratum") in ("defense", "control")]
    m_worlds_manifest = int((manifest or {}).get("m_worlds", M_WORLDS))

    observed_max, landed_total, unpriced = 0, 0, []
    n_defense = n_control = 0
    for t in dc_targets:
        key = (int(t["deck_seed"]), int(t["ply"]))
        p = plies_by_key.get(key)
        m_ok = p["m_worlds_ok"] if p else 0
        m_void = p["m_worlds_void"] if p else 0
        observed_max = max(observed_max, m_ok + m_void)
        landed_total += m_ok
        priced = p is not None and p["family_delta"] is not None
        if not priced:
            unpriced.append(key)
        elif t["stratum"] == "defense":
            n_defense += 1
        elif t["stratum"] == "control":
            n_control += 1
    effective_m = (observed_max if 0 < observed_max < m_worlds_manifest
                  else m_worlds_manifest)
    requested = len(dc_targets) * effective_m
    rate = (landed_total / requested) if requested else 0.0

    ply_priced_ok = not unpriced
    if smoke:
        floor_ok = any((u.get("pair") or {}).get("status") == "OK" for u in units)
        rate_ok = True
        floor_desc = ">=1 unit priced overall (RELAXED-SMOKE)"
    else:
        floor_ok = n_defense >= N_FLOOR and n_control >= N_FLOOR
        rate_ok = rate >= LANDING_RATE_FLOOR
        floor_desc = f"n_defense>={N_FLOOR} AND n_control>={N_FLOOR}"

    ok = ply_priced_ok and floor_ok and rate_ok
    floor_only = (not ok) and (not floor_ok) and ply_priced_ok and rate_ok
    g = _g("G-N", ok, "units/*.json (collapsed by ply) vs targets",
           f"n_defense={n_defense} n_control={n_control} ({floor_desc}); "
           f"unpriced target plies={len(unpriced)} {unpriced[:3]}; "
           f"worlds landed {landed_total}/{requested} ({rate:.4f}) vs floor "
           f"{'RELAXED-SMOKE' if smoke else LANDING_RATE_FLOOR}")
    g["floor_only"] = floor_only
    g["n_defense"] = n_defense
    g["n_control"] = n_control
    g["unpriced_target_plies"] = unpriced
    return g


def gate_decks(units, targets, manifest) -> dict:
    """Every world index in [0, m_worlds); every priced deck_seed is in the
    target file; each unit's n_plies matches its target row's. Band
    conformance is explicitly NOT checked here."""
    m_worlds = int((manifest or {}).get("m_worlds", M_WORLDS))
    target_seeds = {int(t["deck_seed"]) for t in targets}
    target_nplies = {(int(t["deck_seed"]), int(t["ply"])): int(t["n_plies"])
                     for t in targets}
    bad_world, bad_seed, bad_nplies, seeds_seen = [], [], [], []
    for u in units:
        s, ply, w = int(u["deck_seed"]), int(u["ply"]), int(u["world"])
        seeds_seen.append(s)
        if not (0 <= w < m_worlds):
            bad_world.append({"unit": _uid(u), "world": w})
        if s not in target_seeds:
            bad_seed.append({"unit": _uid(u), "deck_seed": s})
        want_np = target_nplies.get((s, ply))
        if want_np is not None and int(u.get("n_plies", -1)) != want_np:
            bad_nplies.append({"unit": _uid(u), "n_plies": u.get("n_plies"),
                              "want": want_np})
    ok = not (bad_world or bad_seed or bad_nplies)
    seed_range = f"[{min(seeds_seen)},{max(seeds_seen)}]" if seeds_seen else "n/a"
    return _g("G-DECKS", ok, "units/*.json vs targets.jsonl",
              f"world indices in [0,{m_worlds}); every priced deck_seed in the "
              f"target file; n_plies consistent. Observed deck_seed range "
              f"{seed_range} — band conformance is NOT checked here (the "
              f"launcher's gate; compare to BAND_CLAIMED)."
              + ("" if ok else f" FAIL bad_world={bad_world[:3]} "
                                f"bad_seed={bad_seed[:3]} bad_nplies={bad_nplies[:3]}"))


def gate_rules(units, manifest) -> dict:
    """Every unit's rules profile == fixed_v1; the manifest's R9 import latch
    observed == expected."""
    bad = [{"unit": _uid(u), "profile": u.get("profile")}
           for u in units if u.get("profile") != RULES_PROFILE]
    r9 = (manifest or {}).get("r9_env") or {}
    r9_ok = (r9.get("r9_env_expected") is not None
            and r9.get("r9_env_expected") == r9.get("r9_env_observed"))
    ok = (not bad) and r9_ok
    return _g("G-RULES", ok, "units/*.json::profile, manifest.json::r9_env",
              f"every unit profile == {RULES_PROFILE!r}; R9 latch observed == "
              f"expected ({r9})" if ok
              else f"DRIFT profile={bad[:3]} r9={r9}")


def gate_void(units) -> dict:
    """void units <= 10% of attempted; no void carries a correctness reason."""
    n_attempt = len(units)
    void_units = [u for u in units if (u.get("pair") or {}).get("status") != "OK"]
    n_void = len(void_units)
    rate = (n_void / n_attempt) if n_attempt else 1.0
    correctness = [u for u in void_units
                   if (u.get("pair") or {}).get("reason") in CORRECTNESS_VOID_REASONS]
    reasons = collections.Counter((u.get("pair") or {}).get("reason")
                                  for u in void_units)
    ok = n_attempt > 0 and (not correctness) and rate <= VOID_RATE_MAX
    return _g("G-VOID", ok, "units/*.json::pair.status,pair.reason",
              f"void {n_void}/{n_attempt} ({rate:.4f}) reasons {dict(reasons)}"
              + (f" ⛔ CORRECTNESS VOIDS {[_uid(u) for u in correctness][:5]}"
                 if correctness else "")
              + ("" if n_attempt else " ABSENT — no units at all"))


def gate_recon(units, primary) -> dict:
    r = recon_primary(units)
    ok = (r is not None and primary.get("diff") is not None
          and abs(r - primary["diff"]) < 1e-9)
    return _g("RECON", ok, "units/*.json (independent flat/sorted/fsum path)",
              f"recon={r!r} vs estimator={primary.get('diff')!r}")


GATES_ORDER = ("G-MANIFEST", "G-LEAF", "G-NEGCTRL", "G-WITNESS", "G-ARMING",
              "G-BUDGET", "G-ROOT", "G-IDENTITY", "G-SELECT", "G-MATCH",
              "G-N", "G-DECKS", "G-RULES", "G-VOID", "RECON")


def run_gates(units, targets, plies, manifest, man_path, targets_path,
             selection, primary, smoke, select_rows_dir=None) -> list[dict]:
    return [
        gate_manifest(manifest, man_path, targets_path),
        gate_leaf(manifest, man_path),
        gate_negctrl(manifest, man_path),
        gate_witness(units),
        gate_arming(units),
        gate_budget(units),
        gate_root(units),
        gate_identity(units),
        gate_select(units, targets, targets_path, manifest, selection,
                   select_rows_dir),
        gate_match(selection, smoke),
        gate_n(plies, units, targets, manifest, smoke),
        gate_decks(units, targets, manifest),
        gate_rules(units, manifest),
        gate_void(units),
        gate_recon(units, primary),
    ]


# --------------------------------------------------------------------------- #
# THE READ RULE (PREREG §7)                                                    #
# --------------------------------------------------------------------------- #
def read_rule(gates, primary, secondary_a) -> dict:
    failing = [g["gate"] for g in gates if g["status"] != "PASS"]
    gn = next((g for g in gates if g["gate"] == "G-N"), None)

    if failing == ["G-N"] and gn is not None and gn.get("floor_only"):
        return {"branch": "SYNTH-HARVEST-SHORT", "failed_gates": failing,
                "licenses": "⛔ NOTHING. Report the achieved n and the "
                            "realized yield. A successor round needs fresh "
                            "owner funding and a fresh band, never a top-up "
                            "of this one."}
    if failing:
        return {"branch": "SYNTH-VOID-INSTRUMENT", "failed_gates": failing,
                "licenses": "⛔ NOTHING. A void is not a null and may never "
                            "be quoted as one. Fix, re-run, read again; the "
                            "voided artefacts stay on disk UNMODIFIED and "
                            "the amended re-read is a new document."}

    d, se, z = primary.get("diff"), primary.get("se"), primary.get("z")
    ub = (d + Z_CRIT * se) if (d is not None and se is not None) else None
    sec_lo, sec_hi = secondary_a.get("ci95_low"), secondary_a.get("ci95_high")
    sec_ci_contains_0 = sec_lo is not None and sec_lo <= 0 <= sec_hi
    res = {"z": z, "mean": d, "se": se, "ci95_upper": ub,
          "bar_clause": BAR_CLAUSE,
          "secondary_a_ci95_contains_0": sec_ci_contains_0}

    if z is not None and z >= Z_CRIT and d is not None and d > 0:
        if d >= BAR_CLAUSE:
            if sec_ci_contains_0:
                res.update(branch="CLAUSE-CORROBORATED", licenses=(
                    "The clause generalises beyond the 28 owner plies. "
                    "Champion-continuation futures do price defense-shaped "
                    "divergences ≈ 0 while an exploit-aware family prices "
                    "them materially higher, on a corpus with no owner in "
                    "it. CL-083 amendment clause 1 becomes a live, general "
                    "limitation on every continuation-priced null in the "
                    "program, and must be carried as such. ⛔ Still "
                    "licenses NOTHING about the owner's edge (§0.1)."))
            else:
                res.update(branch="CLAUSE-CORROBORATED-WEAK", licenses=(
                    "The price IS policy-conditional, but the "
                    "champion-continuation half was not ≈ 0 to begin with. "
                    "Licenses the policy-conditional qualifier; ⛔ the "
                    "\"~0 by construction\" wording must be restated as "
                    "\"materially understated\", because this round "
                    "measured it not to be ~0."))
        else:
            res.update(branch="SYNTH-POSITIVE-SUBTHRESHOLD", licenses=(
                "Named at freeze so the map has no hole. A statistically "
                "nonzero family effect below the decision's own effect "
                "size is not a reason to re-read any existing null. Report "
                "and stop."))
    elif z is not None and z <= -Z_CRIT:
        res.update(branch="SYNTH-NEGATIVE", licenses=(
            "Under an exploit-aware continuation, defense-shaped "
            "divergences price LOWER relative to matched controls than "
            "under the champion continuation — the opposite of the "
            "clause's direction. Report the magnitude; ⛔ do not narrate a "
            "mechanism."))
    elif ub is not None and ub < BAR_CLAUSE:
        res.update(branch="CLAUSE-GENERALITY-REFUTED", licenses=(
            "The clause's GENERALITY is refuted. On 200 matched "
            "defense-shaped divergent synthetic plies, swapping the "
            "continuation family moves the price by less than half the "
            "decision scale the program's continuation bars are written "
            "at. CL-083's amendment clause 1 must be restated as observed "
            "on n = 28 owner plies and NOT reproduced on synthetic plies, "
            "and the E-1b defense by-catch stands as an unreplicated, "
            "possibly owner-specific or chance observation. ⛔ Quote the "
            "bound. ⛔ This does NOT refute the E-1b observation itself, "
            "and does NOT touch measurement/defense_primary_prep/'s "
            "standing read."))
    else:
        res.update(branch="SYNTH-UNRESOLVED", licenses=(
            "NOTHING beyond the achieved bound, which is reported. "
            "Pre-registered at ≈ 36% under a true null (PREREG §4.3). "
            "Re-opening needs more PLIES, not more worlds."))
    res["forbidden_readings"] = FORBIDDEN_READINGS
    return res


# --------------------------------------------------------------------------- #
# RIDERS (PREREG §3.6 / §7.1) — outside every family, never a branch input     #
# --------------------------------------------------------------------------- #
def build_riders(by_s) -> dict:
    defense, control = by_s.get("defense", []), by_s.get("control", [])
    rider_armed = contrast(defense, control, field="price_armed")

    raw_family_delta = {}
    caveat = ("⛔ The raw family delta of a single stratum is NOT the clause; "
             "it is positive by construction (§2.3) and must never be quoted "
             "without its paired stratum beside it.")
    for s in ("defense", "control"):
        cs = cluster_stats(by_s.get(s, []), field="family_delta")
        raw_family_delta[s] = {**cs, "caveat": caveat}

    pooled = [p for p in (defense + control)
             if p.get("price_champ") is not None and p.get("price_armed") is not None]
    rho = _corr([p["price_champ"] for p in pooled],
               [p["price_armed"] for p in pooled])

    def _sd(plies, field):
        vals = [p[field] for p in plies if p.get(field) is not None]
        return statistics.stdev(vals) if len(vals) > 1 else None

    between_ply_sd = {
        "defense": _sd(defense, "family_delta"),
        "control": _sd(control, "family_delta"),
        "pooled": _sd(defense + control, "family_delta"),
    }

    return {
        "armed_defense_minus_control": rider_armed,
        "raw_family_delta": raw_family_delta,
        "cross_family_rho_price_champ_price_armed": rho,
        "between_ply_sd_family_delta": between_ply_sd,
    }


def rider_selfconsistency(by_s) -> dict:
    """delta[champ] expected <= 0 and delta[armed] expected >= 0, per stratum.
    ADVISORY ONLY — search noise / exact-endgame horizon can legitimately
    invert it at small magnitudes."""
    out = {}
    for s in ("defense", "control"):
        plies = [p for p in by_s.get(s, [])
                if p.get("price_champ") is not None and p.get("price_armed") is not None]
        if not plies:
            out[s] = None
            continue
        ok = sum(1 for p in plies if p["price_champ"] <= 0 and p["price_armed"] >= 0)
        out[s] = ok / len(plies)
    return out


def per_arm_cost(units) -> dict:
    arms = [a for u in units for a in (u.get("arms") or {}).values()
           if a.get("status") == "OK"]
    if not arms:
        return {"n_arms": 0}
    return {
        "n_arms": len(arms),
        "mean_s_per_decision": round(statistics.fmean(
            a["s_per_decision"] for a in arms if "s_per_decision" in a), 4),
        "mean_arm_s": round(statistics.fmean(
            a["arm_s"] for a in arms if "arm_s" in a), 3),
        "total_arm_s": round(sum(a.get("arm_s", 0.0) for a in arms), 1),
        "jr_expansions_totals": {
            k: sum(int(((a.get("jr_expansions") or {}).get(k)) or 0) for a in arms)
            for k in JR_KEYS},
    }


# --------------------------------------------------------------------------- #
# main analysis                                                                #
# --------------------------------------------------------------------------- #
def analyse(units, targets, manifest, selection, *, man_path="manifest.json",
           targets_path=None, selection_path="SELECTION.json", smoke=False,
           select_rows_dir=None) -> dict:
    plies = collapse_worlds(units)
    by_s = collections.defaultdict(list)
    for p in plies:
        if p["family_delta"] is not None:
            by_s[p["stratum"]].append(p)

    defense, control = by_s.get("defense", []), by_s.get("control", [])
    primary = contrast(defense, control, field="family_delta")
    secondary_a = contrast(defense, control, field="price_champ")

    gates = run_gates(units, targets, plies, manifest, man_path, targets_path,
                      selection, primary, smoke, select_rows_dir)
    verdict = read_rule(gates, primary, secondary_a)

    witness_gate = next(g for g in gates if g["gate"] == "G-WITNESS")
    identity_units = [u for u in units if u.get("stratum") == "identity"]
    n_identity_exact_zero = sum(
        1 for u in identity_units
        if (u.get("pair") or {}).get("status") == "OK"
        and (u["pair"].get("delta_pts_mover") or {}).get("champ") == 0
        and (u["pair"].get("delta_pts_mover") or {}).get("armed") == 0
        and u["pair"].get("family_delta") == 0)

    riders = build_riders(by_s)
    riders["mean_armed_coverage"] = witness_gate.get("mean_coverage")
    riders["identity_units"] = {"n": len(identity_units),
                                "n_exact_zero": n_identity_exact_zero}
    riders["per_arm_cost"] = per_arm_cost(units)
    riders["rider_selfconsistency"] = rider_selfconsistency(by_s)
    se_ratio = (primary["se"] / SE_MODEL) if primary.get("se") is not None else None
    riders["se_realized_over_modelled"] = se_ratio
    riders["se_ratio_flagged"] = bool(
        se_ratio is not None and not (SE_RATIO_LOW <= se_ratio <= SE_RATIO_HIGH))

    out = {
        "schema": SCHEMA_VERDICT,
        "smoke": bool(smoke),
        "n_units": len(units),
        "n_target_plies": len(targets),
        "n_plies_with_units": len(plies),
        "n_plies_priced": len([p for p in plies if p["family_delta"] is not None]),
        "strata_counts_priced": dict(collections.Counter(
            p["stratum"] for p in plies if p["family_delta"] is not None)),
        "GATES": gates,
        "gates_all_pass": all(g["status"] == "PASS" for g in gates),
        "PRIMARY_defense_minus_control_family_delta": primary,
        "SECONDARY_A_champ_defense_minus_control": secondary_a,
        "RIDERS": riders,
        "VERDICT": verdict,
        "plies": sorted(plies, key=lambda p: (p["stratum"], p["deck_seed"], p["ply"])),
        "caveat": "Every price is a difference of REALIZED final scores over "
                  "CRN-paired continuations under BOTH continuation families "
                  "(champ dose 0.0, armed dose 0.25/mask 31/scope opp), both "
                  "seats, at the PINNED k8x1376 budget. No judge, no "
                  "evaluation function, no search score. It prices the "
                  "TARGET PLY ONLY; every later move is the continuation "
                  "policy's own choice. This instrument prices the CLAUSE, "
                  "never the owner's edge (PREREG §0.1).",
    }
    return out


# --------------------------------------------------------------------------- #
# CLI                                                                          #
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--targets", default=None)
    ap.add_argument("--selection", default=None)
    ap.add_argument("--select-rows", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return selftest()

    missing = [n for n in ("units", "manifest", "targets", "selection")
              if getattr(args, n) is None]
    if missing:
        raise SystemExit(f"--{missing[0].replace('_', '-')} is required")

    units = load_units(args.units)
    targets = load_targets(args.targets)
    manifest = load_json_or_none(args.manifest)
    selection = load_json_or_none(args.selection)

    out = analyse(units, targets, manifest, selection, man_path=args.manifest,
                 targets_path=args.targets, selection_path=args.selection,
                 smoke=args.smoke, select_rows_dir=args.select_rows)

    # ⛔ The artifact is written HERE, never by a shell `| tee`: a pipeline's
    # exit status is tee's, so `--out f | tee f || DIE` could swallow the
    # nonzero exit this whole function exists to produce.
    if args.out:
        Path(args.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k != "plies"}, indent=1))
    if not out["gates_all_pass"]:
        print(f"⛔ GATES FAILED: {[g['gate'] for g in out['GATES'] if g['status'] != 'PASS']}",
              file=sys.stderr)
        raise SystemExit(2)
    print(f"✅ branch={out['VERDICT']['branch']}", file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# --selftest — the defect matrix. Every gate fires on its own named defect,    #
# and only that gate (or the minimal set the defect implies).                  #
# --------------------------------------------------------------------------- #
FIX = DIR / "selftest_fixture"


def _load_fixture():
    units = load_units(FIX / "units")
    targets = load_targets(FIX / "targets_fixture.jsonl")
    manifest = load_json_or_none(FIX / "manifest_fixture.json")
    selection = load_json_or_none(FIX / "SELECTION_fixture.json")
    return units, targets, manifest, selection


def _run(units, targets, manifest, selection, smoke=True):
    return analyse(units, targets, manifest, selection,
                  man_path=str(FIX / "manifest_fixture.json"),
                  targets_path=str(FIX / "targets_fixture.jsonl"),
                  selection_path=str(FIX / "SELECTION_fixture.json"),
                  smoke=smoke)


def _find_unit(units, deck_seed, ply, world):
    for u in units:
        if (u["deck_seed"], u["ply"], u["world"]) == (deck_seed, ply, world):
            return u
    raise KeyError((deck_seed, ply, world))


def selftest() -> int:
    rows = []           # (name, gate_expected, ok, detail)
    fails = []

    u0, t0, m0, s0 = _load_fixture()

    # --- clean fixtures: gates_all_pass under --smoke ------------------------
    out = _run(copy.deepcopy(u0), copy.deepcopy(t0), copy.deepcopy(m0),
              copy.deepcopy(s0), smoke=True)
    ok = out["gates_all_pass"]
    rows.append(("CLEAN gates_all_pass under --smoke", "(none)", ok,
                [g["gate"] for g in out["GATES"] if g["status"] != "PASS"]))
    if not ok:
        fails.append("clean fixtures did not pass all gates under --smoke: "
                     f"{[g['gate'] for g in out['GATES'] if g['status'] != 'PASS']}")

    # --- RECON passes on clean fixtures --------------------------------------
    recon_gate = next(g for g in out["GATES"] if g["gate"] == "RECON")
    rows.append(("RECON passes on clean fixtures", "RECON",
                recon_gate["status"] == "PASS", recon_gate["says"]))
    if recon_gate["status"] != "PASS":
        fails.append(f"RECON did not pass on clean fixtures: {recon_gate}")

    # --- empty units dir exits nonzero (== fails at least one gate) ----------
    out_empty = _run([], copy.deepcopy(t0), copy.deepcopy(m0), copy.deepcopy(s0),
                     smoke=True)
    ok = not out_empty["gates_all_pass"]
    rows.append(("EMPTY units dir fails under --smoke", "(any)", ok,
                [g["gate"] for g in out_empty["GATES"] if g["status"] != "PASS"]))
    if not ok:
        fails.append("an EMPTY units dir passed all gates under --smoke")

    def _mutate_and_check(name, gate, mutate_fn, extra_ok_gates=()):
        """Deep-copy the clean fixture, apply `mutate_fn(units, targets,
        manifest, selection)` in place, re-adjudicate, assert `gate` FAILs
        and the branch is SYNTH-VOID-INSTRUMENT."""
        u, t, m, s = (copy.deepcopy(u0), copy.deepcopy(t0), copy.deepcopy(m0),
                     copy.deepcopy(s0))
        mutate_fn(u, t, m, s)
        out = _run(u, t, m, s, smoke=True)
        failing = {g["gate"] for g in out["GATES"] if g["status"] != "PASS"}
        fired = gate in failing
        branch_ok = out["VERDICT"]["branch"] == "SYNTH-VOID-INSTRUMENT"
        extra_ok = failing <= ({gate} | set(extra_ok_gates))
        ok = fired and branch_ok
        rows.append((name, gate, ok, {"failing": sorted(failing),
                                      "branch": out["VERDICT"]["branch"],
                                      "extra_beyond_expected": sorted(
                                          failing - ({gate} | set(extra_ok_gates)))}))
        if not fired:
            fails.append(f"{name}: expected {gate} to FAIL, failing={failing}")
        if not branch_ok:
            fails.append(f"{name}: expected SYNTH-VOID-INSTRUMENT, "
                        f"got {out['VERDICT']['branch']}")
        if not extra_ok:
            fails.append(f"{name}: unexpected extra gate failures "
                        f"{sorted(failing - ({gate} | set(extra_ok_gates)))}")

    # === G-MANIFEST ===========================================================
    _mutate_and_check(
        "G-MANIFEST: world_seed changed", "G-MANIFEST",
        lambda u, t, m, s: m.__setitem__("world_seed", 1))
    _mutate_and_check(
        "G-MANIFEST: schema changed", "G-MANIFEST",
        lambda u, t, m, s: m.__setitem__("schema", "wrong/v0"))
    _mutate_and_check(
        "G-MANIFEST: targets_sha256 changed", "G-MANIFEST",
        lambda u, t, m, s: m.__setitem__("targets_sha256", "0" * 64),
        extra_ok_gates=("G-SELECT",))     # G-SELECT also asserts this sha

    # === G-LEAF ================================================================
    def _move_leaf(u, t, m, s):
        m["leaf_hash_of_record"] = "deadbeefdeadbeef"
    # ⚠️ leaf_hash_of_record is ALSO one of G-MANIFEST's frozen fields (PREREG
    # §6's gate table lists it explicitly), so moving it legitimately fails
    # both gates at once — belt-and-suspenders by design, not a defect.
    _mutate_and_check("G-LEAF: leaf hash moved", "G-LEAF", _move_leaf,
                      extra_ok_gates=("G-MANIFEST",))

    # === G-NEGCTRL =============================================================
    def _dirty_negctrl(u, t, m, s):
        m["negative_control"]["unarmed_dose0"]["census"] = \
            {"total": 3, "own_mover": 1, "boosted": 1}
    _mutate_and_check("G-NEGCTRL: dose-0 census made nonzero", "G-NEGCTRL",
                      _dirty_negctrl)

    # === G-WITNESS =============================================================
    def _armed_boosted_zero(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_armed__armed"]
        arm["jr_expansions"]["boosted"] = 0
    _mutate_and_check("G-WITNESS: an armed arm's boosted set to 0", "G-WITNESS",
                      _armed_boosted_zero)

    def _champ_census_nonzero(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_champ__champ"]
        arm["jr_expansions"] = {"total": 5, "own_mover": 2, "boosted": 1}
    _mutate_and_check("G-WITNESS: a CHAMP arm's census made nonzero", "G-WITNESS",
                      _champ_census_nonzero)

    def _census_key_deleted(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_armed__armed"]
        del arm["jr_expansions"]["boosted"]
    _mutate_and_check("G-WITNESS: a census key deleted (stale-wheel path)",
                      "G-WITNESS", _census_key_deleted)

    # === G-ARMING ==============================================================
    def _scope_own(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_armed__armed"]
        arm["arming_resolved"]["scope"] = "own"
    _mutate_and_check("G-ARMING: an armed arm's resolved scope changed to 'own'",
                      "G-ARMING", _scope_own)

    # === G-BUDGET ==============================================================
    def _kdets16(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_armed__armed"]
        arm["arming_resolved"]["k_dets"] = 16
    _mutate_and_check("G-BUDGET: an arm's resolved k_dets set to 16", "G-BUDGET",
                      _kdets16)

    # === G-ROOT ================================================================
    def _root_sha_changed(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_armed__armed"]
        arm["witness"]["root_repr_sha"] = "SOMETHING_ELSE"
    _mutate_and_check("G-ROOT: one arm's root_repr_sha changed", "G-ROOT",
                      _root_sha_changed)

    def _det_seed_within_family(u, t, m, s):
        arm = _find_unit(u, 999900000002, 114, 0)["arms"]["pick_armed__armed"]
        arm["witness"]["det_seed_base_at_root"] = 999999
    _mutate_and_check("G-ROOT: det_seed_base changed WITHIN a family", "G-ROOT",
                      _det_seed_within_family)

    # === G-IDENTITY ============================================================
    def _identity_leak(u, t, m, s):
        unit = _find_unit(u, 999900000001, 124, 0)
        unit["pair"]["family_delta"] = 1
    _mutate_and_check("G-IDENTITY: an identity unit's family_delta set to 1",
                      "G-IDENTITY", _identity_leak)

    # === G-SELECT ==============================================================
    # ⚠️ a stray deck_seed is ALSO not in the target file, so it legitimately
    # fails G-DECKS's "every priced deck_seed appears in the target file"
    # check too — both gates are watching the same fact from two documents.
    def _stray_unit(u, t, m, s):
        clone = copy.deepcopy(_find_unit(u, 999900000002, 114, 0))
        clone["deck_seed"] = 424242
        clone["ply"] = 1
        u.append(clone)
    _mutate_and_check("G-SELECT: a stray unit added", "G-SELECT", _stray_unit,
                      extra_ok_gates=("G-DECKS",))

    # ⚠️ in this fixture every deck_seed maps to exactly one target ply, so
    # dropping a target row also strands that deck_seed's units outside
    # G-DECKS's "every priced deck_seed appears in the target file" check.
    def _dropped_target(u, t, m, s):
        t.pop(0)
    _mutate_and_check("G-SELECT: a target row dropped", "G-SELECT",
                      _dropped_target, extra_ok_gates=("G-DECKS",))

    # === G-N ===================================================================
    def _ply_wiped(u, t, m, s):
        u[:] = [x for x in u
               if not (x["deck_seed"] == 999900000002 and x["ply"] == 114)]
    # ⚠️ a target ply with zero unit files is also "missing" from G-SELECT's
    # priced-vs-target set comparison — both gates correctly notice.
    _mutate_and_check("G-N: a target ply's units all removed", "G-N", _ply_wiped,
                      extra_ok_gates=("G-SELECT",))

    # === G-DECKS ================================================================
    def _bad_world(u, t, m, s):
        _find_unit(u, 999900000002, 114, 0)["world"] = 99
    _mutate_and_check("G-DECKS: a world index set to 99", "G-DECKS", _bad_world)

    # === G-RULES ================================================================
    def _bad_profile(u, t, m, s):
        _find_unit(u, 999900000002, 114, 0)["profile"] = "walled"
    _mutate_and_check("G-RULES: a unit's profile set to 'walled'", "G-RULES",
                      _bad_profile)

    # === G-VOID ==================================================================
    def _correctness_void(u, t, m, s):
        unit = _find_unit(u, 999900000002, 114, 0)
        unit["pair"] = {"status": "VOID", "reason": "root_identity_mismatch"}
    _mutate_and_check("G-VOID: a unit's pair.status set to VOID/"
                      "root_identity_mismatch", "G-VOID", _correctness_void,
                      extra_ok_gates=("G-ROOT",))   # the void unit also drops
                                                     # out of G-ROOT's checked set

    # --- print the table -------------------------------------------------------
    print(f"{'CASE':<62} {'GATE':<12} {'RESULT':<6}")
    for name, gate, ok, detail in rows:
        print(f"{name:<62} {gate:<12} {'PASS' if ok else 'FAIL'}")
        if not ok:
            print(f"    detail: {detail}")

    print(json.dumps({"selftest": "synth_mech adjudicator", "n_cases": len(rows),
                      "n_failed": len(fails), "failures": fails,
                      "PASS": not fails}, indent=1))
    if fails:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
