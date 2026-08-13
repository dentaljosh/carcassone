#!/usr/bin/env python3
"""CAPABILITY PROBE for the denial / open-city / sims-split overnight chains.

Spec: `measurement/night_chain_20260812/RUNBOOK.md`; the chain that calls this is
`scripts/classical_search/denial_simsplit_chain.sh`. The open-city mode's spec is
`measurement/opencity_term_20260812/TERM_SPEC.md` §6 (its manual wheel step) + §7, and
`measurement/opencity_term_20260812/CALIB_READ_RULE.md` §4 names this probe a **launch
blocker, not a nicety**.

THE ONE SAFETY PROPERTY THIS FILE OWNS
--------------------------------------
Both blocks of that chain measure a knob that landed AFTER the currently-installed
`carc_rs` wheel was built. If a candidate arm's knob is silently absent from the loaded
build, the cell still runs, still completes, still writes a clean manifest -- and
produces a **beautiful, meaningless null**: candidate == champion, margin z ~ 0, and
nothing in the output says so. That is strictly worse than a crash, because it enters
the record as evidence.

So: every knob is probed for **three** things, and any miss is a hard non-zero exit.

  1. the knob EXISTS on the Python side (dataclass field / harness CLI flag);
  2. the knob is ACCEPTED by the loaded native build (`carc_rs.LeafConfigRs` kwargs --
     `rust_agent.leaf_config_rs` forwards denial/open-city kwargs ONLY when the dose is
     nonzero, precisely so a stale build raises `TypeError` instead of serving a
     default-off leaf);
  3. the knob CHANGES THE NUMBER. (1) and (2) are structure; only (3) excludes
     "accepted and ignored". For denial we play a few short scripted games through the
     rust mirror and require that at least one leaf value MOVES at the requested dose,
     while the dose-0.0 identity control stays bit-identical on every sampled value.

`--require opencity` runs the same three, on BOTH leaves, plus a fourth the denial mode
does not have:

  4. dose 0.0 with the thresholds deliberately MOVED off their defaults is BIT-EXACT with
     the champion -- TERM_SPEC §6's `opencity-d0-identity` cell -- on the rust leaf AND on
     the python leaf. This is the control for the opposite failure: a threshold knob that
     leaks into the leaf while the dose gate is closed would make every rung of a dose
     ladder a mixture of a dose effect and a threshold effect, and no arm of the §7
     calibration could be read.

`--require jrules` is the same four checks again, for the J-rules-on-search bundle
(`measurement/jrules_on_search_20260813/DESIGN.md` §11 **G4**, which names this mode a
launch-blocking gate for the same reason: "a cell that quietly runs champion-vs-champion
produces a beautiful, meaningless null"). Its analogue of open-city's MOVED THRESHOLDS is
the **`jrules_mask`** -- dose 0.0 with the mask moved off `JR_ALL` must still be
bit-exact with the champion, because the dose gates the whole bundle. Two jrules-only
notes: the bundle is a BONUS and the leaf **ADDS** `dose * T` (denial/open-city subtract),
and the ladder `{0.5, 1.0, 2.0}` is pre-registered in DESIGN §7 *with its expected leaf
hashes* (§9), so this mode ALSO checks the hashes it computes on this box against those.

`--require simsplit` can do (1) and the fixed-total arithmetic, but NOT (3): pick
equality under a re-split budget is a game-level property and this probe plays no games.
That gap is why the chain ALSO hard-gates block S1 on a hand-written go-file -- the
human attests the byte-identity gate; the probe attests the flags exist.

The probe is read-only: no games, no band, no governance file, no results.csv.

Usage (the chain's two calls):
  chain_capability_probe.py --require denial --doses 1.0,2.0 --size-min 5 --open-max 3 \
      --cells-out /mnt/c/carc-shared/night_chain_20260812/d1_cells.tsv --json-out ...
  chain_capability_probe.py --require simsplit --harness scripts/classical_search/eval_fair_puct.py \
      --sims-tile 2064 --sims-meeple 688 --sims 1376 --json-out ...

and the open-city arms of `CALIB_READ_RULE.md` §1 (A=4/2, B=3/2, C=6/3; symmetric held True):

  chain_capability_probe.py --require opencity --doses 0.5,2.0 --size-min 4 --edge-min 2 \
      --cells-out .../oc_cells_A.tsv --json-out ...

and the J-rules bundle (DESIGN.md §7's pre-registered ladder is the default, §9's
`jrules_mask` default 31 == JR_ALL is the primary cell):

  chain_capability_probe.py --require jrules
  chain_capability_probe.py --require jrules --doses 1.0 --mask 27 --json-out ...

⚠️ The CALLER must export the champion leaf env before invoking this (the launcher env
canon). `DEFAULT_CONFIG` is resolved at `virtual_score_v2` import time, so the probe
asserts the champion hash is `a36d2e15a3b3d71d` -- that assert is what proves the caller's
env canon is the champion and not something the shell mangled.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

CHAMP_LEAF_HASH = "a36d2e15a3b3d71d"

# Playout budget for the functional (dose-moves-the-number) probe. Denial cells bite on
# 8.4%-16.4% of leaf values (reconcile_leaf --configs denial, 2026-08-11), so a few
# hundred sampled values is a very safe margin for "at least one differs".
PROBE_SEEDS = ("880011", "880012", "880013")
PROBE_MAX_PLIES = 150
PROBE_EVERY = 3

# The four open-city knobs (measurement/opencity_term_20260812/TERM_SPEC.md §5). NOTE the
# units trap: `opencity_size_min` is in DISTINCT TILES, while denial's `denial_size_min` is
# in city POINTS. Same-looking flag, different axis -- do not carry a value across.
OPENCITY_KNOBS = ("opencity_dose", "opencity_size_min", "opencity_edge_min",
                  "opencity_symmetric")

# TERM_SPEC §6's `opencity-d0-identity` cell: the dose is OFF but every other knob is
# deliberately MOVED off its default. `opencity_dose` gates the whole term, so this MUST be
# bit-identical to the champion on both leaves. If it is not, the gate leaks and every rung
# of a dose ladder is a mixture of a dose effect and a threshold effect.
OPENCITY_D0_IDENTITY = {"opencity_dose": 0.0, "opencity_size_min": 2.0,
                        "opencity_edge_min": 1, "opencity_symmetric": False}

# The two J-rules knobs (measurement/jrules_on_search_20260813/DESIGN.md §5). NOTE the
# SIGN trap: this bundle is a BONUS potential and the leaf ADDS `jrules_dose * T`, where
# denial and open-city SUBTRACT their penalties -- so "a bigger dose" does not mean "more
# discouragement", and a dose carried across from either of those terms means nothing here.
JRULES_KNOBS = ("jrules_dose", "jrules_mask")

# `flat_leaf.JR_ALL` == JR_J1|JR_J2|JR_J5|JR_J6|JR_J8, and `flat_leaf.JR_J5`. Held as
# literals so the pure helpers keep working with no leaf import -- and so a silent
# renumbering of the rule bits surfaces here as a test failure rather than as an ablation
# nobody ordered.
JR_ALL = 31
JR_J5 = 4

# DESIGN §7's PRE-REGISTERED dose ladder. denial/opencity deliberately have no default
# dose, because their arm is chosen per-run by Joshua out of an offline calibration and a
# defaulted one would measure a cell nobody registered. This ladder is the opposite case:
# it is written into the spec (with its read-rule, FUND-SMALLEST) before any number was
# read, so defaulting to it smuggles in nothing. `--doses` still overrides.
JRULES_LADDER = "0.5,1.0,2.0"

# DESIGN §9's expected `cand_leaf_hash` per ladder rung, computed under the launcher env
# canon. Recomputing them ON THIS BOX is pre-flight item 4 of §9's launch block ("O0"),
# and it is a strictly stronger statement than `cand_hash_moves`: it proves the env canon
# AND the spec construction together reproduce the number the design committed to.
JRULES_PREREGISTERED_HASHES = {0.5: "46a7652670123027",
                               1.0: "a87fb6801b81d588",
                               2.0: "56db6c2247dee55f"}

# The jrules analogue of TERM_SPEC §6's `opencity-d0-identity` cell: the dose is OFF but
# the OTHER knob is deliberately MOVED off its default (27 == JR_ALL minus JR_J5, i.e. the
# J5 unclaimed-value rule dropped). `jrules_dose` gates the whole bundle, so this MUST be
# bit-identical to the champion on both leaves. If it is not, the gate leaks and every rung
# of a dose ladder is a mixture of a dose effect and a mask effect.
JRULES_D0_IDENTITY = {"jrules_dose": 0.0, "jrules_mask": JR_ALL - JR_J5}


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested in tests/test_night_chain_helpers.py)              #
# --------------------------------------------------------------------------- #
def parse_doses(spec: str, max_cells: int = 4) -> list[float]:
    """`"1.0,2.0"` -> `[1.0, 2.0]`, with the chain's fail-loud rules applied.

    Refuses: empty/absent, non-numeric, duplicates, more than `max_cells`, negative,
    and 0.0. A 0.0 dose is byte-identical to the champion leaf (the term is
    default-off), so it is an IDENTITY control, not a dose -- it would silently
    make the "candidate hash must differ from the champion" gate unsatisfiable.
    Running one is a separate, deliberately-specified cell, never a chain default.
    """
    if spec is None or not str(spec).strip():
        raise ValueError(
            "no doses given. DENIAL_DOSES is REQUIRED and has no default: the doses are "
            "chosen by Joshua from the offline calibration, and a defaulted dose would "
            "silently measure a cell nobody pre-registered.")
    out: list[float] = []
    for tok in str(spec).replace(" ", "").split(","):
        if not tok:
            continue
        try:
            d = float(tok)
        except ValueError as e:
            raise ValueError(f"dose {tok!r} is not a number") from e
        if d < 0:
            raise ValueError(f"dose {d} is negative; denial doses are >= 0")
        if d == 0.0:
            raise ValueError(
                "dose 0.0 is the IDENTITY control (byte-identical to the champion leaf), "
                "not a dose. This chain refuses it: its candidate leaf hash would equal "
                "the champion's and the wiring gate could not distinguish it from a "
                "silently-default-off cell.")
        if d in out:
            raise ValueError(f"duplicate dose {d}")
        out.append(d)
    if not out:
        raise ValueError("no doses parsed from DENIAL_DOSES")
    if len(out) > max_cells:
        raise ValueError(f"{len(out)} doses given; this chain supports 1..{max_cells} cells")
    return out


def _num_tag(x: float) -> str:
    """`1.0 -> '1p0'`, `0.5 -> '0p5'`, `3 -> '3'` -- filesystem/exp-id safe."""
    s = ("%g" % float(x))
    return s.replace(".", "p").replace("-", "m")


def cell_tag(dose: float, size_min: float, open_max: int, prefix: str = "d1_denial") -> str:
    """Stable per-cell directory / exp-id stem. Carries BOTH thresholds, because two
    doses at different thresholds are different cells and must never share a dir."""
    return f"{prefix}_d{_num_tag(dose)}_s{_num_tag(size_min)}_o{_num_tag(open_max)}"


def cand_leaf_spec(dose: float, size_min: float, open_max: int) -> dict:
    """The `--cand-leaf-json` object for one denial cell (replace-fields on
    DEFAULT_CONFIG). Thresholds are ALWAYS written, even at their built defaults, so
    the cell JSON on disk is self-describing rather than implying a default."""
    return {"denial_dose": float(dose),
            "denial_size_min": float(size_min),
            "denial_open_max": int(open_max)}


def opencity_cell_tag(dose: float, size_min: float, edge_min: int, symmetric: bool,
                      prefix: str = "oc") -> str:
    """Stable per-cell directory / exp-id stem for an OPEN-CITY cell.

    Deliberately unlike `cell_tag`'s `_s<..>_o<..>`: the size axis here is TILES (`t`), the
    openness axis is a MINIMUM (`e`), and the symmetry flag is part of the leaf, so all
    three ride in the tag. Two cells can then never share a directory -- including the pair
    that differs only in `opencity_symmetric`, which is a DIFFERENT TERM (TERM_SPEC §3), not
    a rung on the same ladder."""
    return (f"{prefix}_d{_num_tag(dose)}_t{_num_tag(size_min)}_e{_num_tag(edge_min)}"
            f"_{'sym' if symmetric else 'asym'}")


def opencity_cand_leaf_spec(dose: float, size_min: float, edge_min: int,
                            symmetric: bool) -> dict:
    """The `--cand-leaf-json` object for one open-city cell (replace-fields on
    DEFAULT_CONFIG). ALL FOUR knobs are always written, even at their built defaults, so
    the cell JSON on disk is self-describing rather than implying a default -- the same
    rule `cand_leaf_spec` states for denial.

    Refuses the thresholds `c5_leaf_override._assert_cy_float_path` refuses, here rather
    than 40 minutes into a cell: `edge_min < 1` would make `open_n >= edge_min` price EVERY
    incomplete city (a different term, TERM_SPEC §5), and `size_min < 1` is not a city."""
    if int(edge_min) < 1:
        raise ValueError(
            f"opencity_edge_min must be >= 1 (got {edge_min}); below 1 the predicate "
            f"`open_n >= edge_min` fires on every incomplete city, which is a DIFFERENT "
            f"term rather than a rung on this ladder (TERM_SPEC §5). c5_leaf_override "
            f"raises on it too, so such a cell could never run anyway.")
    if float(size_min) < 1.0:
        raise ValueError(f"opencity_size_min must be >= 1 distinct TILE (got {size_min}); "
                         f"c5_leaf_override raises on it too.")
    return {"opencity_dose": float(dose),
            "opencity_size_min": float(size_min),
            "opencity_edge_min": int(edge_min),
            "opencity_symmetric": bool(symmetric)}


def jrules_cell_tag(dose: float, mask: int, prefix: str = "jr") -> str:
    """Stable per-cell directory / exp-id stem for a J-RULES cell.

    Carries the mask as well as the dose, because a mask ablation at the same dose is a
    DIFFERENT candidate leaf (a different subset of the interview), not a rung on the dose
    ladder -- so the two must never share a directory."""
    return f"{prefix}_d{_num_tag(dose)}_m{_num_tag(mask)}"


def jrules_cand_leaf_spec(dose: float, mask: int) -> dict:
    """The `--cand-leaf-json` object for one J-rules cell (replace-fields on
    DEFAULT_CONFIG). BOTH knobs are always written, even at their built defaults, so the
    cell JSON on disk is self-describing rather than implying a default -- the same rule
    `cand_leaf_spec` / `opencity_cand_leaf_spec` state.

    (DESIGN §8's wiring gate O4' asks that `jrules_mask` be ABSENT from the deploy cell
    JSON so a mask typo cannot silently ablate rules. An explicit `31` satisfies that
    intent and is bit-identical AND hash-identical to omitting it -- the field is
    excluded-if-default in every hash dialect -- which is exactly what the
    `cand_hash_preregistered` check below pins against DESIGN §9's published hashes.)

    Refuses the two masks that would make a cell unreadable rather than merely different:
    a mask with no rule bits set, and a mask carrying bits no rule defines."""
    m = int(mask)
    if m <= 0:
        raise ValueError(
            f"jrules_mask must select at least one rule (got {mask}); mask 0 makes the "
            f"whole bundle identically zero, so the candidate arm IS the champion while "
            f"still hashing differently -- the `cand_hash_moves` gate could not catch it "
            f"and the cell would read as a beautiful, meaningless null.")
    if m > JR_ALL:
        raise ValueError(
            f"jrules_mask {mask} carries bits above JR_ALL={JR_ALL} (J1|J2|J5|J6|J8). Both "
            f"leaves mask with `&`, so the extra bits are silently DROPPED: the cell would "
            f"run as mask {m & JR_ALL} while its JSON claims {mask}. A typo, not a cell.")
    return {"jrules_dose": float(dose), "jrules_mask": m}


def check_split_total(sims_tile: int, sims_meeple: int, sims: int) -> tuple[bool, str]:
    """The sims-split screen is a RE-ALLOCATION at fixed per-turn budget, not a budget
    change: a champion turn runs two searches (tile, then meeple) at `sims` per
    determinization each, so the per-turn per-determinization total is `2 * sims`.
    A split that does not sum to that is measuring budget AND allocation at once --
    a confound the lever's whole premise is about avoiding."""
    want = 2 * int(sims)
    got = int(sims_tile) + int(sims_meeple)
    if got != want:
        return False, (f"sims_tile+sims_meeple = {sims_tile}+{sims_meeple} = {got}, but the "
                       f"fixed per-turn total at the production budget is 2*{sims} = {want}. "
                       f"A non-matching split confounds re-allocation with a budget change.")
    if sims_tile <= 0 or sims_meeple <= 0:
        return False, "both arms of the split must be > 0 sims"
    return True, f"fixed-total OK: {sims_tile}+{sims_meeple} == 2*{sims} == {want}"


def harness_has_flags(help_text: str, flags: list[str]) -> tuple[bool, list[str]]:
    """Which of `flags` the harness's own `--help` advertises. argparse prints every
    option string it defines, so this is an authoritative existence check -- it reads
    the LOADED harness, not the repo's source tree (they can differ mid-merge)."""
    missing = [f for f in flags if f not in help_text]
    return (not missing), missing


# --------------------------------------------------------------------------- #
# Runtime probes                                                              #
# --------------------------------------------------------------------------- #
def _import_leaf_bits():
    """Import order matters: the leaf env must already be exported by the caller."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))          # c5_leaf_override
    from c5_leaf_override import _leaf_hash, _load_cand_leaf_cfg      # noqa: E402
    from carcassonne_ai.virtual_score_v2 import DEFAULT_CONFIG        # noqa: E402
    return DEFAULT_CONFIG, _leaf_hash, _load_cand_leaf_cfg


def probe_denial(doses, size_min, open_max, runtime: bool) -> dict:
    r = {"capability": "denial", "checks": [], "cells": [], "ok": False}

    def chk(name, ok, detail=""):
        r["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    default_cfg, leaf_hash, load_cand = _import_leaf_bits()

    # --- (1) the Python side carries the knob at all -------------------------------
    has_fields = all(hasattr(default_cfg, f)
                     for f in ("denial_dose", "denial_size_min", "denial_open_max"))
    ok = chk("py_leafconfig_fields", has_fields,
             "LeafConfig.denial_dose/_size_min/_open_max present"
             if has_fields else "LeafConfig has no denial fields -- this tree predates the term")
    try:
        from carcassonne_ai import flat_leaf
        ok &= chk("py_flat_denial_term", hasattr(flat_leaf, "flat_denial_term"),
                  "flat_leaf.flat_denial_term present")
    except Exception as e:                                            # pragma: no cover
        ok &= chk("py_flat_denial_term", False, f"import failed: {e!r}")

    # --- (2) the caller's env canon really is the champion -------------------------
    champ_hash = leaf_hash(default_cfg)
    r["champ_leaf_hash"] = champ_hash
    ok &= chk("env_is_champion_leaf", champ_hash == CHAMP_LEAF_HASH,
              f"DEFAULT_CONFIG hash {champ_hash} (want {CHAMP_LEAF_HASH})")

    # --- (3) per-cell specs + hashes; every one must MOVE off the champion ---------
    seen = {}
    for d in doses:
        spec = cand_leaf_spec(d, size_min, open_max)
        cfg = load_cand(json.dumps(spec))
        h = leaf_hash(cfg)
        tag = cell_tag(d, size_min, open_max)
        r["cells"].append({"tag": tag, "dose": d, "size_min": size_min,
                           "open_max": open_max, "cand_leaf_json": json.dumps(spec),
                           "cand_leaf_hash": h})
        ok &= chk(f"cand_hash_moves[{tag}]", h != champ_hash,
                  f"candidate leaf hash {h} != champion {champ_hash}")
        ok &= chk(f"cand_hash_unique[{tag}]", h not in seen,
                  f"{h} not already used by {seen.get(h, '-')}")
        seen[h] = tag

    if not runtime:
        r["runtime_probe"] = "SKIPPED (--no-runtime-probe: dry-run mode)"
        r["ok"] = ok
        return r

    # --- (4) the LOADED native build accepts the kwargs ----------------------------
    # This is the fail-closed seam: rust_agent.leaf_config_rs forwards denial kwargs
    # only for a nonzero dose, so a pre-denial wheel raises TypeError HERE instead of
    # quietly serving the champion leaf to the candidate arm.
    try:
        import carc_rs
        from carcassonne_ai.rust_agent import leaf_config_rs
        r["carc_rs_path"] = getattr(carc_rs, "__file__", "?")
        probe_cfg = load_cand(json.dumps(cand_leaf_spec(doses[0], size_min, open_max)))
        rs_cand = leaf_config_rs(probe_cfg)
        rs_champ = leaf_config_rs(default_cfg)
        ok &= chk("carc_rs_accepts_denial_kwargs", True,
                  "carc_rs.LeafConfigRs built with denial kwargs")
    except TypeError as e:
        r["ok"] = False
        chk("carc_rs_accepts_denial_kwargs", False,
            f"the LOADED carc_rs build PREDATES the denial term ({e}). Rebuild + install "
            f"the combined wheel on this box (maturin develop --release) before this block "
            f"runs. Refusing: a default-off candidate arm produces a meaningless null.")
        return r
    except Exception as e:                                            # pragma: no cover
        r["ok"] = False
        chk("carc_rs_accepts_denial_kwargs", False, f"probe failed: {e!r}")
        return r

    # --- (5) the term is WIRED INTO THE LEAF, not merely accepted -------------------
    try:
        st = carc_rs.MirrorState.from_seed(PROBE_SEEDS[0])
        terms = st.leaf_terms(0, rs_champ)
        ok &= chk("carc_rs_exposes_denial_term", "denial_term" in terms,
                  f"leaf_terms keys: {sorted(terms)}")
    except Exception as e:                                            # pragma: no cover
        ok &= chk("carc_rs_exposes_denial_term", False, f"{e!r}")

    moved = same = 0
    identity_breaks = 0
    try:
        rs_identity = leaf_config_rs(default_cfg)     # dose stays 0 -> no kwargs forwarded
        for seed in PROBE_SEEDS:
            st = carc_rs.MirrorState.from_seed(seed)
            for ply in range(PROBE_MAX_PLIES):
                if st.is_terminal():
                    break
                if ply % PROBE_EVERY == 0:
                    for p in (0, 1):
                        a = st.leaf_value_float(p, rs_champ)
                        b = st.leaf_value_float(p, rs_cand)
                        c = st.leaf_value_float(p, rs_identity)
                        moved += int(a != b)
                        same += int(a == b)
                        identity_breaks += int(a != c)
                acts = st.legal_actions()
                if not acts:
                    break
                st.advance(acts[(ply * 7 + 3) % len(acts)])
    except Exception as e:                                            # pragma: no cover
        ok &= chk("carc_rs_denial_changes_leaf", False, f"playout probe failed: {e!r}")
    else:
        r["functional"] = {"values_moved": moved, "values_same": same,
                           "identity_control_breaks": identity_breaks}
        ok &= chk("carc_rs_denial_changes_leaf", moved > 0,
                  f"{moved} of {moved + same} sampled leaf values MOVE at dose {doses[0]} "
                  f"(0 would mean accepted-and-ignored == a silently default-off candidate)")
        ok &= chk("carc_rs_identity_control", identity_breaks == 0,
                  f"{identity_breaks} champion-vs-champion mismatches (must be 0)")

    r["ok"] = bool(ok)
    return r


def probe_opencity(doses, size_min, edge_min, symmetric, runtime: bool) -> dict:
    """The denial probe's structure, applied to the four open-city knobs, plus the dose-0
    bit-exactness control that denial has no analogue for (see the module docstring, (4))."""
    r = {"capability": "opencity", "checks": [], "cells": [], "ok": False}

    def chk(name, ok, detail=""):
        r["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    default_cfg, leaf_hash, load_cand = _import_leaf_bits()

    # --- (1) the Python side carries the knob at all -------------------------------
    has_fields = all(hasattr(default_cfg, f) for f in OPENCITY_KNOBS)
    ok = chk("py_leafconfig_fields", has_fields,
             "LeafConfig.opencity_dose/_size_min/_edge_min/_symmetric present"
             if has_fields else
             f"LeafConfig is missing {[f for f in OPENCITY_KNOBS if not hasattr(default_cfg, f)]}"
             f" -- this tree predates the term")
    try:
        from carcassonne_ai import flat_leaf
        ok &= chk("py_flat_opencity_term", hasattr(flat_leaf, "flat_opencity_term"),
                  "flat_leaf.flat_opencity_term present")
    except Exception as e:                                            # pragma: no cover
        ok &= chk("py_flat_opencity_term", False, f"import failed: {e!r}")

    # --- (2) the caller's env canon really is the champion -------------------------
    champ_hash = leaf_hash(default_cfg)
    r["champ_leaf_hash"] = champ_hash
    ok &= chk("env_is_champion_leaf", champ_hash == CHAMP_LEAF_HASH,
              f"DEFAULT_CONFIG hash {champ_hash} (want {CHAMP_LEAF_HASH})")

    # --- (3) per-cell specs + hashes; every one must MOVE off the champion ---------
    seen = {}
    for d in doses:
        spec = opencity_cand_leaf_spec(d, size_min, edge_min, symmetric)
        cfg = load_cand(json.dumps(spec))
        h = leaf_hash(cfg)
        tag = opencity_cell_tag(d, size_min, edge_min, symmetric)
        r["cells"].append({"tag": tag, "dose": d, "size_min": float(size_min),
                           "edge_min": int(edge_min), "symmetric": bool(symmetric),
                           "cand_leaf_json": json.dumps(spec), "cand_leaf_hash": h})
        ok &= chk(f"cand_hash_moves[{tag}]", h != champ_hash,
                  f"candidate leaf hash {h} != champion {champ_hash}")
        ok &= chk(f"cand_hash_unique[{tag}]", h not in seen,
                  f"{h} not already used by {seen.get(h, '-')}")
        seen[h] = tag

    # --- the dose-0 identity control's HASH: observed, never assumed ---------------
    # `_LEAF_HASH_EXCLUDE_IF_DEFAULT` carries all four open-city fields, but it drops a
    # field only while that field holds its DEFAULT value. This cell moves three of them,
    # so whether it hashes AS the champion is an empirical question -- recorded here as a
    # report field, not gated: the GATE is the bit-exactness of the leaf VALUES below.
    d0_cfg = load_cand(json.dumps(OPENCITY_D0_IDENTITY))
    d0_hash = leaf_hash(d0_cfg)
    d0_hash_eq = (d0_hash == champ_hash)
    d0_note = (
        f"leaf_hash(dose-0 + MOVED thresholds) == champion ({champ_hash}): all four knobs "
        f"are excluded-if-default AND the moved ones evidently do not survive into the "
        f"hashed dict."
        if d0_hash_eq else
        f"leaf_hash(dose-0 + MOVED thresholds) = {d0_hash} != champion {champ_hash}: "
        f"_LEAF_HASH_EXCLUDE_IF_DEFAULT drops a field only while it holds its DEFAULT "
        f"value, so the three MOVED thresholds stay in the hashed dict even though the "
        f"dose gate makes the leaf VALUES bit-identical. Consequence for the chain: a cell "
        f"whose dose was accidentally zeroed would still PASS `cand_hash_moves` -- the hash "
        f"gate cannot catch it, and `parse_doses`' refusal of dose 0.0 is the gate that "
        f"does.")
    r["dose0_identity"] = {"cand_leaf_json": json.dumps(OPENCITY_D0_IDENTITY),
                           "leaf_hash": d0_hash, "hash_equals_champion": d0_hash_eq,
                           "note": d0_note}

    if not runtime:
        r["runtime_probe"] = "SKIPPED (--no-runtime-probe: dry-run mode)"
        r["ok"] = ok
        return r

    # --- (4) the LOADED native build accepts the kwargs ----------------------------
    # Same fail-closed seam as denial: rust_agent.leaf_config_rs forwards the open-city
    # kwargs only for a nonzero dose, so a pre-open-city wheel raises TypeError HERE
    # instead of quietly serving the champion leaf to the candidate arm. CALIB_READ_RULE
    # §4 calls this the launch blocker; TERM_SPEC §6's manual step is the fix.
    try:
        import carc_rs
        from carcassonne_ai.rust_agent import leaf_config_rs
        r["carc_rs_path"] = getattr(carc_rs, "__file__", "?")
        probe_cfg = load_cand(json.dumps(
            opencity_cand_leaf_spec(doses[0], size_min, edge_min, symmetric)))
        rs_cand = leaf_config_rs(probe_cfg)
        rs_champ = leaf_config_rs(default_cfg)
        rs_d0 = leaf_config_rs(d0_cfg)      # dose 0.0 -> no kwargs forwarded, any build
        ok &= chk("carc_rs_accepts_opencity_kwargs", True,
                  "carc_rs.LeafConfigRs built with opencity kwargs")
    except TypeError as e:
        r["ok"] = False
        chk("carc_rs_accepts_opencity_kwargs", False,
            f"the LOADED carc_rs build PREDATES the open-city term ({e}). Rebuild + install "
            f"the combined wheel on this box (maturin develop --release) before this block "
            f"runs. Refusing: a default-off candidate arm produces a meaningless null.")
        return r
    except Exception as e:                                            # pragma: no cover
        r["ok"] = False
        chk("carc_rs_accepts_opencity_kwargs", False, f"probe failed: {e!r}")
        return r

    # --- (5) the term is WIRED INTO THE LEAF, not merely accepted -------------------
    try:
        st = carc_rs.MirrorState.from_seed(PROBE_SEEDS[0])
        terms = st.leaf_terms(0, rs_champ)
        ok &= chk("carc_rs_exposes_opencity_term", "opencity_term" in terms,
                  f"leaf_terms keys: {sorted(terms)}")
    except Exception as e:                                            # pragma: no cover
        ok &= chk("carc_rs_exposes_opencity_term", False, f"{e!r}")

    # --- (6) + (7) the rust leaf: dose MOVES it, dose 0 does NOT --------------------
    # TERM_SPEC §6 measured the golden-corpus bite at 21.9% for the spec thresholds
    # (4 tiles / 2 edges) and 0.0% at 6 tiles / 3 edges -- the tight arm can legitimately
    # fail this check, and that is a fact about the arm, not a bug to be papered over.
    moved = same = 0
    identity_breaks = 0
    d0_seen = d0_breaks = 0
    try:
        rs_identity = leaf_config_rs(default_cfg)     # dose stays 0 -> no kwargs forwarded
        for seed in PROBE_SEEDS:
            st = carc_rs.MirrorState.from_seed(seed)
            for ply in range(PROBE_MAX_PLIES):
                if st.is_terminal():
                    break
                if ply % PROBE_EVERY == 0:
                    for p in (0, 1):
                        a = st.leaf_value_float(p, rs_champ)
                        b = st.leaf_value_float(p, rs_cand)
                        c = st.leaf_value_float(p, rs_identity)
                        z = st.leaf_value_float(p, rs_d0)
                        moved += int(a != b)
                        same += int(a == b)
                        identity_breaks += int(a != c)
                        d0_breaks += int(a.hex() != z.hex())
                        d0_seen += 1
                acts = st.legal_actions()
                if not acts:
                    break
                st.advance(acts[(ply * 7 + 3) % len(acts)])
    except Exception as e:                                            # pragma: no cover
        ok &= chk("carc_rs_opencity_changes_leaf", False, f"playout probe failed: {e!r}")
    else:
        r["functional"] = {"values_moved": moved, "values_same": same,
                           "identity_control_breaks": identity_breaks,
                           "rs_dose0_values_compared": d0_seen, "rs_dose0_breaks": d0_breaks}
        ok &= chk("carc_rs_opencity_changes_leaf", moved > 0,
                  f"{moved} of {moved + same} sampled leaf values MOVE at dose {doses[0]} "
                  f"(size_min={size_min} TILES, edge_min={edge_min}, symmetric={symmetric}); "
                  f"0 would mean accepted-and-ignored == a silently default-off candidate, "
                  f"OR a predicate this arm's thresholds never satisfy (TERM_SPEC §6 "
                  f"measured 0.0% bite at 6 tiles / 3 edges)")
        ok &= chk("carc_rs_identity_control", identity_breaks == 0,
                  f"{identity_breaks} champion-vs-champion mismatches (must be 0)")
        ok &= chk("carc_rs_dose0_bit_exact", d0_breaks == 0 and d0_seen > 0,
                  f"{d0_seen - d0_breaks}/{d0_seen} sampled RUST leaf values are bit-identical "
                  f"to the champion's at {OPENCITY_D0_IDENTITY} (the dose gate holds with the "
                  f"thresholds moved). {d0_note}")

    # --- (7b) the PYTHON leaf: same two properties, on its own scripted playouts ----
    # The chain's cells run --backend rust, but the python leaf is the reference the
    # reconcile gate calls bit-exact, and c5_leaf_override builds the candidate LeafConfig
    # through it -- so a python-side gate leak would be invisible to (6)/(7) above.
    py_seen = py_breaks = 0
    py_moved = py_same = 0
    try:
        import random as _random

        import numpy as _np
        from carcassonne_ai import flat_leaf as _fl
        from carcassonne_ai.game_wrapper import Game as _Game
        cand_cfg = load_cand(json.dumps(
            opencity_cand_leaf_spec(doses[0], size_min, edge_min, symmetric)))
        for seed in PROBE_SEEDS:
            _random.seed(int(seed))
            g = _Game(enable_legal_moves_cache=True)
            bd = g.get_init_board()
            for ply in range(PROBE_MAX_PLIES):
                if g.get_game_ended(bd, 0) != 0.0:
                    break
                if ply % PROBE_EVERY == 0:
                    for p in (0, 1):
                        ref = _fl.flat_virtual_score_v2_float(bd.state, p, default_cfg)
                        z = _fl.flat_virtual_score_v2_float(bd.state, p, d0_cfg)
                        b = _fl.flat_virtual_score_v2_float(bd.state, p, cand_cfg)
                        py_breaks += int(ref.hex() != z.hex())
                        py_seen += 1
                        py_moved += int(ref.hex() != b.hex())
                        py_same += int(ref.hex() == b.hex())
                legal = _np.flatnonzero(g.get_valid_moves(bd))
                if not len(legal):
                    break
                bd, _ = g.get_next_state(bd, int(legal[(ply * 7 + 3) % len(legal)]))
    except Exception as e:                                            # pragma: no cover
        ok &= chk("py_dose0_bit_exact", False, f"python playout probe failed: {e!r}")
    else:
        r.setdefault("functional", {}).update(
            {"py_dose0_values_compared": py_seen, "py_dose0_breaks": py_breaks,
             "py_values_moved": py_moved, "py_values_same": py_same})
        ok &= chk("py_dose0_bit_exact", py_breaks == 0 and py_seen > 0,
                  f"{py_seen - py_breaks}/{py_seen} sampled PYTHON leaf values are "
                  f"bit-identical (.hex()) to the champion's at {OPENCITY_D0_IDENTITY}")
        ok &= chk("py_opencity_changes_leaf", py_moved > 0,
                  f"{py_moved} of {py_moved + py_same} sampled PYTHON leaf values MOVE at "
                  f"dose {doses[0]} (same caveat as the rust check: a tight arm can "
                  f"legitimately never fire)")

    r["ok"] = bool(ok)
    return r


def probe_jrules(doses, mask, runtime: bool) -> dict:
    """The open-city probe's structure, applied to the two J-rules knobs: the same three
    checks on BOTH leaves plus the dose-0 bit-exactness control (here the MOVED knob is the
    `jrules_mask`, not a threshold), and one addition -- the candidate hashes are checked
    against DESIGN §9's PRE-REGISTERED values where the rung is one of §7's ladder."""
    r = {"capability": "jrules", "checks": [], "cells": [], "ok": False}

    def chk(name, ok, detail=""):
        r["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    default_cfg, leaf_hash, load_cand = _import_leaf_bits()

    # --- (1) the Python side carries the knob at all -------------------------------
    has_fields = all(hasattr(default_cfg, f) for f in JRULES_KNOBS)
    ok = chk("py_leafconfig_fields", has_fields,
             "LeafConfig.jrules_dose/_mask present" if has_fields else
             f"LeafConfig is missing {[f for f in JRULES_KNOBS if not hasattr(default_cfg, f)]}"
             f" -- this tree predates the term")
    try:
        from carcassonne_ai import flat_leaf
        ok &= chk("py_flat_jrules_term", hasattr(flat_leaf, "flat_jrules_term"),
                  "flat_leaf.flat_jrules_term present")
        # The rule bits are the mask's whole meaning; a renumbering would turn every
        # recorded mask into a different ablation without changing a single cell JSON.
        bits_ok = (getattr(flat_leaf, "JR_ALL", None) == JR_ALL
                   and getattr(flat_leaf, "JR_J5", None) == JR_J5)
        ok &= chk("py_rule_bits_unmoved", bits_ok,
                  f"flat_leaf.JR_ALL={getattr(flat_leaf, 'JR_ALL', None)} (want {JR_ALL}), "
                  f"JR_J5={getattr(flat_leaf, 'JR_J5', None)} (want {JR_J5})")
    except Exception as e:                                            # pragma: no cover
        ok &= chk("py_flat_jrules_term", False, f"import failed: {e!r}")

    # --- (2) the caller's env canon really is the champion -------------------------
    champ_hash = leaf_hash(default_cfg)
    r["champ_leaf_hash"] = champ_hash
    ok &= chk("env_is_champion_leaf", champ_hash == CHAMP_LEAF_HASH,
              f"DEFAULT_CONFIG hash {champ_hash} (want {CHAMP_LEAF_HASH})")

    # --- (3) per-cell specs + hashes; every one must MOVE off the champion ---------
    seen = {}
    for d in doses:
        spec = jrules_cand_leaf_spec(d, mask)
        cfg = load_cand(json.dumps(spec))
        h = leaf_hash(cfg)
        tag = jrules_cell_tag(d, mask)
        want = JRULES_PREREGISTERED_HASHES.get(float(d)) if int(mask) == JR_ALL else None
        r["cells"].append({"tag": tag, "dose": d, "mask": int(mask),
                           "cand_leaf_json": json.dumps(spec), "cand_leaf_hash": h,
                           "preregistered_hash": want})
        ok &= chk(f"cand_hash_moves[{tag}]", h != champ_hash,
                  f"candidate leaf hash {h} != champion {champ_hash}")
        ok &= chk(f"cand_hash_unique[{tag}]", h not in seen,
                  f"{h} not already used by {seen.get(h, '-')}")
        if want is not None:
            ok &= chk(f"cand_hash_preregistered[{tag}]", h == want,
                      f"{h} == DESIGN §9's published hash for dose {d}" if h == want else
                      f"{h} != DESIGN §9's published {want} for dose {d}. Either the env "
                      f"canon is not the champion's, or the leaf moved under the design -- "
                      f"in both cases the cell would measure something other than the "
                      f"pre-registered one.")
        seen[h] = tag

    # --- the dose-0 identity control's HASH: observed, never assumed ---------------
    # Both knobs sit in `_LEAF_HASH_EXCLUDE_IF_DEFAULT`, but a field is dropped only while
    # it holds its DEFAULT value, and this cell moves the mask. So whether it hashes AS the
    # champion is an empirical question -- reported, not gated: the GATE is the
    # bit-exactness of the leaf VALUES below.
    d0_cfg = load_cand(json.dumps(JRULES_D0_IDENTITY))
    d0_hash = leaf_hash(d0_cfg)
    d0_hash_eq = (d0_hash == champ_hash)
    d0_note = (
        f"leaf_hash(dose-0 + MOVED mask) == champion ({champ_hash}): both knobs are "
        f"excluded-if-default AND the moved mask evidently does not survive into the "
        f"hashed dict."
        if d0_hash_eq else
        f"leaf_hash(dose-0 + MOVED mask) = {d0_hash} != champion {champ_hash}: "
        f"_LEAF_HASH_EXCLUDE_IF_DEFAULT drops a field only while it holds its DEFAULT "
        f"value, so the moved mask stays in the hashed dict even though the dose gate makes "
        f"the leaf VALUES bit-identical. Consequence for the chain: a cell whose dose was "
        f"accidentally zeroed would still PASS `cand_hash_moves` -- the hash gate cannot "
        f"catch it, and `parse_doses`' refusal of dose 0.0 is the gate that does.")
    r["dose0_identity"] = {"cand_leaf_json": json.dumps(JRULES_D0_IDENTITY),
                           "leaf_hash": d0_hash, "hash_equals_champion": d0_hash_eq,
                           "note": d0_note}

    if not runtime:
        r["runtime_probe"] = "SKIPPED (--no-runtime-probe: dry-run mode)"
        r["ok"] = ok
        return r

    # --- (4) the LOADED native build accepts the kwargs ----------------------------
    # Same fail-closed seam as denial/open-city: rust_agent.leaf_config_rs forwards the
    # jrules kwargs only for a nonzero dose, so a pre-jrules wheel raises TypeError HERE
    # instead of quietly serving the champion leaf to the candidate arm. DESIGN §11 G3/G4.
    try:
        import carc_rs
        from carcassonne_ai.rust_agent import leaf_config_rs
        r["carc_rs_path"] = getattr(carc_rs, "__file__", "?")
        probe_cfg = load_cand(json.dumps(jrules_cand_leaf_spec(doses[0], mask)))
        rs_cand = leaf_config_rs(probe_cfg)
        rs_champ = leaf_config_rs(default_cfg)
        rs_d0 = leaf_config_rs(d0_cfg)      # dose 0.0 -> no kwargs forwarded, any build
        ok &= chk("carc_rs_accepts_jrules_kwargs", True,
                  "carc_rs.LeafConfigRs built with jrules kwargs")
    except TypeError as e:
        r["ok"] = False
        chk("carc_rs_accepts_jrules_kwargs", False,
            f"the LOADED carc_rs build PREDATES the J-rules term ({e}). Rebuild + install "
            f"the combined wheel on this box (maturin develop --release) before this block "
            f"runs. Refusing: a default-off candidate arm produces a meaningless null.")
        return r
    except Exception as e:                                            # pragma: no cover
        r["ok"] = False
        chk("carc_rs_accepts_jrules_kwargs", False, f"probe failed: {e!r}")
        return r

    # --- (5) the term is WIRED INTO THE LEAF, not merely accepted -------------------
    try:
        st = carc_rs.MirrorState.from_seed(PROBE_SEEDS[0])
        terms = st.leaf_terms(0, rs_champ)
        ok &= chk("carc_rs_exposes_jrules_term", "jrules_term" in terms,
                  f"leaf_terms keys: {sorted(terms)}")
    except Exception as e:                                            # pragma: no cover
        ok &= chk("carc_rs_exposes_jrules_term", False, f"{e!r}")

    # --- (6) + (7) the rust leaf: dose MOVES it, dose 0 does NOT --------------------
    # Unlike open-city's arm C, no pre-registered jrules cell is expected to read zero
    # bite: DESIGN §6 measured J6 firing on 98% of a random-play corpus and J2 on 83%
    # (J8 alone is nearly inert at 3%, which is why a mask that selects ONLY J8 can
    # legitimately fail this check -- a fact about that ablation, not a bug).
    moved = same = 0
    identity_breaks = 0
    d0_seen = d0_breaks = 0
    try:
        rs_identity = leaf_config_rs(default_cfg)     # dose stays 0 -> no kwargs forwarded
        for seed in PROBE_SEEDS:
            st = carc_rs.MirrorState.from_seed(seed)
            for ply in range(PROBE_MAX_PLIES):
                if st.is_terminal():
                    break
                if ply % PROBE_EVERY == 0:
                    for p in (0, 1):
                        a = st.leaf_value_float(p, rs_champ)
                        b = st.leaf_value_float(p, rs_cand)
                        c = st.leaf_value_float(p, rs_identity)
                        z = st.leaf_value_float(p, rs_d0)
                        moved += int(a != b)
                        same += int(a == b)
                        identity_breaks += int(a != c)
                        d0_breaks += int(a.hex() != z.hex())
                        d0_seen += 1
                acts = st.legal_actions()
                if not acts:
                    break
                st.advance(acts[(ply * 7 + 3) % len(acts)])
    except Exception as e:                                            # pragma: no cover
        ok &= chk("carc_rs_jrules_changes_leaf", False, f"playout probe failed: {e!r}")
    else:
        r["functional"] = {"values_moved": moved, "values_same": same,
                           "identity_control_breaks": identity_breaks,
                           "rs_dose0_values_compared": d0_seen, "rs_dose0_breaks": d0_breaks}
        ok &= chk("carc_rs_jrules_changes_leaf", moved > 0,
                  f"{moved} of {moved + same} sampled leaf values MOVE at dose {doses[0]} "
                  f"(mask={mask}); 0 would mean accepted-and-ignored == a silently "
                  f"default-off candidate, OR a mask whose rules never fire (DESIGN §6 "
                  f"measured J8 alone at 3%)")
        ok &= chk("carc_rs_identity_control", identity_breaks == 0,
                  f"{identity_breaks} champion-vs-champion mismatches (must be 0)")
        ok &= chk("carc_rs_dose0_bit_exact", d0_breaks == 0 and d0_seen > 0,
                  f"{d0_seen - d0_breaks}/{d0_seen} sampled RUST leaf values are bit-identical "
                  f"to the champion's at {JRULES_D0_IDENTITY} (the dose gate holds with the "
                  f"mask moved). {d0_note}")

    # --- (7b) the PYTHON leaf: same two properties, on its own scripted playouts ----
    # The chain's cells run --backend rust, but the python leaf is the reference the
    # reconcile gate calls bit-exact, and c5_leaf_override builds the candidate LeafConfig
    # through it -- so a python-side gate leak would be invisible to (6)/(7) above. It is
    # also the ONLY leg that exercises `_jrules_off()`: a set dose must leave the cy fast
    # path, and a cy build that served the champion leaf here would show up as zero bite.
    py_seen = py_breaks = 0
    py_moved = py_same = 0
    try:
        import random as _random

        import numpy as _np
        from carcassonne_ai import flat_leaf as _fl
        from carcassonne_ai.game_wrapper import Game as _Game
        cand_cfg = load_cand(json.dumps(jrules_cand_leaf_spec(doses[0], mask)))
        for seed in PROBE_SEEDS:
            _random.seed(int(seed))
            g = _Game(enable_legal_moves_cache=True)
            bd = g.get_init_board()
            for ply in range(PROBE_MAX_PLIES):
                if g.get_game_ended(bd, 0) != 0.0:
                    break
                if ply % PROBE_EVERY == 0:
                    for p in (0, 1):
                        ref = _fl.flat_virtual_score_v2_float(bd.state, p, default_cfg)
                        z = _fl.flat_virtual_score_v2_float(bd.state, p, d0_cfg)
                        b = _fl.flat_virtual_score_v2_float(bd.state, p, cand_cfg)
                        py_breaks += int(ref.hex() != z.hex())
                        py_seen += 1
                        py_moved += int(ref.hex() != b.hex())
                        py_same += int(ref.hex() == b.hex())
                legal = _np.flatnonzero(g.get_valid_moves(bd))
                if not len(legal):
                    break
                bd, _ = g.get_next_state(bd, int(legal[(ply * 7 + 3) % len(legal)]))
    except Exception as e:                                            # pragma: no cover
        ok &= chk("py_dose0_bit_exact", False, f"python playout probe failed: {e!r}")
    else:
        r.setdefault("functional", {}).update(
            {"py_dose0_values_compared": py_seen, "py_dose0_breaks": py_breaks,
             "py_values_moved": py_moved, "py_values_same": py_same})
        ok &= chk("py_dose0_bit_exact", py_breaks == 0 and py_seen > 0,
                  f"{py_seen - py_breaks}/{py_seen} sampled PYTHON leaf values are "
                  f"bit-identical (.hex()) to the champion's at {JRULES_D0_IDENTITY}")
        ok &= chk("py_jrules_changes_leaf", py_moved > 0,
                  f"{py_moved} of {py_moved + py_same} sampled PYTHON leaf values MOVE at "
                  f"dose {doses[0]} (same caveat as the rust check: a mask whose rules "
                  f"never fire can legitimately read zero)")

    r["ok"] = bool(ok)
    return r


def probe_simsplit(harness: str, sims_tile, sims_meeple, sims, allow_unequal: bool,
                   runtime: bool) -> dict:
    r = {"capability": "simsplit", "checks": [], "ok": False, "harness": harness}

    def chk(name, ok, detail=""):
        r["checks"].append({"check": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    ok = True
    ok &= chk("harness_exists", os.path.exists(harness), harness)
    if os.path.exists(harness) and runtime:
        py = os.environ.get("CHAIN_PY", sys.executable)
        try:
            p = subprocess.run([py, harness, "--help"], capture_output=True, text=True,
                               timeout=300)
            help_text = (p.stdout or "") + (p.stderr or "")
        except Exception as e:                                        # pragma: no cover
            help_text = ""
            chk("harness_help_ran", False, f"{e!r}")
        got, missing = harness_has_flags(help_text, ["--sims-tile", "--sims-meeple"])
        ok &= chk("harness_has_split_flags", got,
                  "both flags advertised by argparse" if got else
                  f"MISSING {missing} -- the per-phase sims knob has NOT landed on this "
                  f"harness. Block S1 SKIPS (it does not fail the chain).")
    elif not runtime:
        r["runtime_probe"] = "SKIPPED (--no-runtime-probe: dry-run mode)"

    if sims_tile is not None and sims_meeple is not None and sims is not None:
        good, msg = check_split_total(sims_tile, sims_meeple, sims)
        if allow_unequal and not good:
            chk("fixed_per_turn_total", True, f"OVERRIDDEN by --allow-unequal-total: {msg}")
        else:
            ok &= chk("fixed_per_turn_total", good, msg)

    # Deliberately NOT claimed here: bit-exactness of the split knob at the production
    # setting. That is a game-level property, this probe plays no games, and the chain
    # therefore ALSO requires a hand-written go-file for S1 (see the RUNBOOK).
    r["not_probeable_here"] = ("byte-identity of --sims-tile/--sims-meeple at the production "
                               "setting; attested by the hand-written S1 go-file, never by "
                               "this script")
    r["ok"] = bool(ok)
    return r


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--require", choices=("denial", "opencity", "jrules", "simsplit"),
                    required=True)
    ap.add_argument("--doses", default=None,
                    help="denial/opencity: comma list, REQUIRED, no default. jrules: "
                         f"optional -- defaults to DESIGN §7's pre-registered ladder "
                         f"{JRULES_LADDER}")
    ap.add_argument("--size-min", type=float, default=None,
                    help="denial: min city POINTS. opencity: min DISTINCT TILES -- different "
                         "axis, do not carry a value across")
    ap.add_argument("--open-max", type=int, default=None, help="denial only")
    ap.add_argument("--edge-min", type=int, default=None,
                    help="opencity only: min open_n for the penalty to fire; must be >= 1")
    ap.add_argument("--asymmetric", action="store_true",
                    help="opencity only: T = pen(self) instead of pen(self) - pen(opp). OFF by "
                         "default => opencity_symmetric=True, which CALIB_READ_RULE §1 holds "
                         "in every arm (flipping it is a different term, not a rung)")
    ap.add_argument("--mask", type=int, default=JR_ALL,
                    help=f"jrules only: rule bitmask J1|J2|J5|J6|J8. Default {JR_ALL} == "
                         f"JR_ALL == the primary cell (DESIGN §8); anything else is an "
                         f"ABLATION, and its cells carry the mask in their tag")
    ap.add_argument("--max-cells", type=int, default=4)
    ap.add_argument("--harness", default=None)
    ap.add_argument("--sims-tile", type=int, default=None)
    ap.add_argument("--sims-meeple", type=int, default=None)
    ap.add_argument("--sims", type=int, default=None, help="production sims per determinization")
    ap.add_argument("--allow-unequal-total", action="store_true")
    ap.add_argument("--no-runtime-probe", action="store_true",
                    help="structure + arithmetic only; skips carc_rs and the harness --help "
                         "(what --dry-run uses)")
    ap.add_argument("--cells-out", default=None,
                    help="denial: write a TSV of tag<TAB>cand_leaf_json<TAB>cand_leaf_hash "
                         "(the per-box launchers read exactly this file)")
    ap.add_argument("--json-out", default=None)
    a = ap.parse_args()

    runtime = not a.no_runtime_probe
    try:
        if a.require == "denial":
            if a.size_min is None or a.open_max is None:
                raise ValueError("--size-min and --open-max are REQUIRED for denial and have "
                                 "no default (DENIAL_SIZE_MIN / DENIAL_OPEN_MAX)")
            doses = parse_doses(a.doses, a.max_cells)
            rep = probe_denial(doses, a.size_min, a.open_max, runtime)
        elif a.require == "opencity":
            if a.size_min is None or a.edge_min is None:
                raise ValueError("--size-min (DISTINCT TILES) and --edge-min are REQUIRED for "
                                 "opencity and have no default: the arm is chosen by Joshua "
                                 "from CALIB_READ_RULE §1 (A=4/2, B=3/2, C=6/3), and a "
                                 "defaulted threshold would silently measure a cell nobody "
                                 "pre-registered")
            doses = parse_doses(a.doses, a.max_cells)
            rep = probe_opencity(doses, a.size_min, a.edge_min, not a.asymmetric, runtime)
        elif a.require == "jrules":
            # The ONE mode with a defaulted dose list, and only because DESIGN §7 wrote the
            # ladder down (with its FUND-SMALLEST read-rule) before any number was read.
            # Recorded in the report either way, so no cell's provenance is implied.
            doses = parse_doses(a.doses if a.doses else JRULES_LADDER, a.max_cells)
            rep = probe_jrules(doses, a.mask, runtime)
            rep["doses_source"] = ("--doses" if a.doses else
                                   f"DEFAULT: DESIGN §7 pre-registered ladder {JRULES_LADDER}")
        else:
            if not a.harness:
                raise ValueError("--harness is required for the simsplit probe")
            rep = probe_simsplit(a.harness, a.sims_tile, a.sims_meeple, a.sims,
                                 a.allow_unequal_total, runtime)
    except Exception as e:
        rep = {"capability": a.require, "ok": False,
               "checks": [{"check": "arguments", "ok": False, "detail": str(e)}]}

    if a.cells_out and rep.get("cells"):
        p = Path(a.cells_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w") as f:
            for c in rep["cells"]:
                f.write(f"{c['tag']}\t{c['cand_leaf_json']}\t{c['cand_leaf_hash']}\n")
        rep["cells_out"] = str(p)
    if a.json_out:
        p = Path(a.json_out)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rep, indent=2))

    print(json.dumps(rep, indent=2))
    for c in rep.get("checks", []):
        if not c["ok"]:
            print(f"[probe] FAIL {c['check']}: {c['detail']}", file=sys.stderr)
    return 0 if rep.get("ok") else 7


if __name__ == "__main__":
    raise SystemExit(main())
