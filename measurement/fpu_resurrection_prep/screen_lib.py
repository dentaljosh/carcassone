#!/usr/bin/env python3
"""`screen_lib` — the FPU-RESURRECTION round's shared instrument library.

⭐ **A FORK of `measurement/phasegate_prep/screen_lib.py`**, carrying the
hardened parts verbatim in construction (`cross_box_rev_gate` — the IS-A1 fold —
`rev_matches`, `is_hex40`, `host_matches_box`, `paired_margin`, `winrate_elo`,
`recon_close`, `resolve`/`gate`) and REWRITING the parts that are round-specific.
`DESIGN.md` §7 names the fork and names the gates that must NOT be copied:

  ⛔ **`G-DECKS` — REWRITTEN AGAIN, AND IN THE OPPOSITE DIRECTION.** Phasegate's
     ranges OVERLAPPED by design (one deck set, decomposed). ⭐ THIS ROUND'S
     THREE CELLS ARE ON THREE SEPARATE BANDS and their ranges are DISJOINT by
     construction — each cell is its own question against the same unmodified
     champion, and nothing is pooled across them. A copied overlap clause would
     pass vacuously; a copied phasegate `G-SUBPOOL` has nothing to gate.
  ⛔ **`G-SINGLEVAR` — REWRITTEN.** Phasegate could demand that EVERY search
     knob be equal across the two sides, because its single variable lived in a
     separate `cand_tiearb` container. ⭐ HERE THE SINGLE VARIABLE IS ITSELF A
     SEARCH KNOB: on `CELL_CPUCT10` the candidate's `c_puct` MUST differ from
     the opponent's. So the alias set is PER CELL, and the knob the cell owns is
     asserted DIFFERENT while every other alias is asserted EQUAL. An unedited
     copy would void the very cell it was written to protect.
  ⭐ **`G-FPU` / `G-CPUCT` — NEW, and they are this round's inverted-liveness
     pair.** Neither knob moves a leaf hash, so a moved-hash check proves
     nothing; and — the whole reason this round exists — `fpu_reduction` was
     UNREACHABLE until 2026-08-29 (`rust_agent.search_config_rs` passed a
     HARD-CODED `None`). A cell run over that defect is champion-vs-champion
     wearing a candidate's name and reads as a perfectly healthy null.
  ⭐ **`G-TWOSIDED` — NEW, the SECOND witness.** `G-FPU` proves the knob was
     REQUESTED (`config.cand_search`, written from the CLI). `G-TWOSIDED` reads
     the RESOLVED `HeuristicPriorConfig` of EACH SIDE
     (`config.champion.*` vs `config.opponent.champ_cfg.*`) and proves the value
     landed on the candidate and NOWHERE ELSE. Two independent addresses, one
     derived from the request and one from the constructed agents — the same
     `G-GATE`/`G-PHI` discipline phasegate used, adapted to a knob whose
     liveness has no per-ply fire counter to read.

⛔⛔ **IS-D1 IS BINDING ON EVERY ADDRESS.** Config-shaped values resolve from
`manifest.json`; statistics from `summary.json`, **which carries no config block
at all**. `resolve()` returns the ADDRESS that answered and every gate prints it.

⛔ **ABSENT IS FAIL, never a skip and never a default** (`READ_RULE.md` §4).
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

# =========================================================================== #
# 0. FROZEN CONSTANTS — the pair is law; these restate it, they do not decide  #
# =========================================================================== #

#: `DESIGN.md` §5. ⛔ PROPOSED, NOT CLAIMED at build time. THREE bands, one per
#: cell: each cell is its own question and nothing is pooled across them, so a
#: shared band would buy nothing and would spend one band's retirement on three
#: verdicts. Tree sweep 2026-08-29: 0 references to any of the three.
#: ⚠️⚠️ `146000000000` IS THE TRAP THIS ORDER EXISTS FOR — absent from
#: `governance/BAND_REGISTRY.csv` but carrying references in the tree. The
#: registry is NECESSARY AND NOT SUFFICIENT; the TREE SWEEP is the binding check
#: and is re-run immediately before the CSV append. ⛔ `158e9` and `160e9` were
#: DROPPED from consideration for exactly that reason (incidental tree hits).
BANDS = {"CELL_FPU02": 155_000_000_000,
         "CELL_FPU04": 156_000_000_000,
         "CELL_CPUCT10": 157_000_000_000}
#: The sub-range the §9 smoke plays. ⛔ NEVER in any band claim — it buys no
#: decks of the round. Placed at the TOP of the HIGHEST band's 1e9 space, ~1e9
#: seeds above every cell's range (the phasegate convention: 154999999000 sat
#: inside band 154e9 the same way).
THROWAWAY_BASE = 157_999_999_000
THROWAWAY_SPAN = 1000

#: `DESIGN.md` §2 — identical on BOTH sides of every cell.
LEAF_HASH = "a36d2e15a3b3d71d"
LEAF_CURVE125 = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
#: ⭐⭐ THE BUDGET, PROMOTED 2026-08-30 (owner; desktop champion 11008 -> 22016).
#: ⛔ This is the CURRENT champion config and both sides run it. `run_cells.sh`
#: RE-ASSERTS it against `governance/PRODUCTION.yaml` at launch (`G-PROD`) rather
#: than trusting this restatement — a frozen budget that has silently drifted
#: from the champion is a cell measuring a knob against a stale opponent.
#: ⭐ NOTE FOR THE MECHANISM: the promotion is pure WIDTH. `sims_per_det` is
#: UNCHANGED at 1376, and FPU acts INSIDE one determinization tree (it scores
#: unvisited children on that tree's PUCT descent). So per-tree first-visit
#: behaviour at 22016 is IDENTICAL to 11008; `k_dets` only changes HOW MANY such
#: trees are pooled. The mechanism argument is budget-agnostic — see DESIGN §2.2.
K_DETS, SIMS_PER_DET, TOTAL_SIMS = 16, 1376, 22016
EXACT_K, EXACT_MODE = 2, "marginalized"
RULES_PROFILE = "fixed_v1"
BACKEND = "rust"

#: `READ_RULE.md` §4 `G-SAT` — a RAIL check, not a strength bar.
SAT_BAND = (0.35, 0.65)
#: `READ_RULE.md` §4 `G-N`.
N_COMMON_FLOOR_FRACTION = 0.80
FAILURE_RATE_VOID = 0.02

#: `DESIGN.md` §3 — the sizing constant, carried from the Stage-2 Phase B cell
#: `ARB` (`M +3.0700`, `paired_z +4.445`, `n_paired 400 DECKS`) exactly as
#: phasegate carried it. ⛔ POWER ARITHMETIC ONLY: `READ_RULE.md` §1 forbids it
#: as a denominator in any branch test — every branch is adjudicated at the
#: cell's OWN REALIZED SE.
SIGMA_D_MODEL = 13.81
#: Flag (never void) a realized/modelled SE ratio outside this band.
SE_ANOMALY_BAND = (0.70, 1.43)

#: ⭐ THE BARS. `READ_RULE.md` §5.
#: The round is funded at n=400 decks / 800 games per cell, whose 2σ resolution
#: is ±1.381 pts/deck on the margin and ±17.4 elo — the brief's "~±17.5 elo".
#: `BAR_M` IS that resolution: `F-RESURRECT` requires an effect at least as
#: large as the smallest one this design can see, so the branch can never fire
#: on an effect the instrument could not have resolved.
BRANCH_Z = 2.0
BAR_M = 1.381                #: pts/deck — 2 * SIGMA_D_MODEL / sqrt(400)
BAR_ELO = 17.4               #: the SECONDARY's matching resolution. ⚠️ NEVER a
#:                              branch input on its own — see RIDERS.

#: ⭐ R4 (2026-08-30, pre-launch merge review) — **THE ELO FOOTING.**
#: `BAR_ELO` is the **DECK-PAIRED** 2σ resolution: 800 games are 400 decks × 2
#: seatings, and pairing scales the sigma by `1/sqrt(2)`. The textbook binomial
#: sigma `winrate_elo` computes is the **UNPAIRED** one (±24.6 at 2σ, n=800), so
#: quoting it beside a paired bar compared two different rulers — the bar looked
#: clearable when the CI said it was not, and vice versa. The PAIRED footing is
#: the correct one (it is the footing the primary margin already uses), so the
#: emitted sigma carries this factor and every emitted field says so in its NAME.
#: ⛔ This changes NO branch: `branch_for_cell` keys off `M`/`z`/`UB95` vs
#: `BAR_M` and never sees an elo. `sanity_check()` re-derives `BAR_ELO` from
#: `elo_sigma_paired` so the constant can never drift from the arithmetic again.
PAIRING_FACTOR = 1.0 / math.sqrt(2.0)          #: ≈ 0.70711

#: `RECON` tolerance (`READ_RULE.md` §1.1).
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

#: ⛔⛔ PRIOR ART. DESCRIPTIVE OVERLAYS ONLY (`READ_RULE.md` §1.2) — never
#: pooled, never z-combined, never a gate input, and every one of them is
#: CROSS-ERA as well as cross-band, which is strictly worse than the cross-band
#: over-dispersion CL-068 measured.
#: ⚠️⚠️ `docs/LEVER_INDEX.md:146` RECORDS THIS AXIS AS **CLOSED**. This round is
#: a deliberate REOPENING and `DESIGN.md` §1 owes the argument: every prior FPU
#: cell measured FPU on a NEURAL or VALUE-BLENDED agent, and none of them could
#: have measured it on the classical champion, because the knob was structurally
#: unreachable on the champion's backend until 2026-08-29.
PRIOR_ART = {
    "verdict_fpu02_paired_n200 (2026-06-02)": {
        "elo": 45.4, "sigma": 24.5, "z": 1.85, "n_games": 200,
        "agent": "NeuralMCTS, pathb_loop/ckpt/iter_11.pt priors + v2_7 leaf, c=3.0",
        "note": "a SCREEN (z<2), never confirmed; results.csv row 68"},
    "verdict_fpu04_paired_n200 (2026-06-02)": {
        "elo": 31.4, "sigma": 24.5, "z": 1.28, "n_games": 200,
        "agent": "same, fpu 0.4",
        "note": "a SCREEN (z<2), never confirmed; results.csv row 69"},
    "m3 FPU curve (2026-07-02/03, results.csv rows 233-236)": {
        "winrates": {0.4: 0.391, 0.6: 0.496, 0.8: 0.4825, 1.0: 0.476},
        "n_games": 400, "agent": "iter_02+warmstart ADDITIVE value-blend b=0.27 "
                                 "vs pure-v2.9 anchor, sims=100, band 6.0e9",
        "note": "⛔ THE STRONGEST PRIOR AGAINST THIS ROUND: the curve PEAKS AT "
                "PARITY (0.496 at fpu 0.6) and rolls off. Recorded reading: "
                "'FPU removes the weak value's HARM but cannot make it EXCEED' "
                "the anchor. ⚠️ It measures FPU as a RESCUE for a bad learned "
                "value, on a 100-sim neural agent — NOT as a lever on the "
                "classical champion's 1376-sim heuristic-prior search."},
}


# =========================================================================== #
# 1. THE CELLS                                                                 #
# =========================================================================== #

@dataclass(frozen=True)
class CellSpec:
    """One archive = one cell = one band. ⛔ Nothing is pooled in this round."""
    name: str
    role: str                       #: "local" | "laptop" — `G-HOST`'s frozen box
    knob: str                       #: "fpu_reduction" | "c_puct"
    value: float                    #: `G-FPU`/`G-CPUCT`'s frozen expectation
    seed_start: int
    n_decks: int
    purpose: str

    @property
    def n_games(self) -> int:
        return self.n_decks * 2

    @property
    def seed_end(self) -> int:
        """INCLUSIVE last seed of this cell's own range."""
        return self.seed_start + self.n_decks - 1

    @property
    def cand_fpu(self):
        """The candidate's RESOLVED fpu_reduction. `None` == the champion."""
        return self.value if self.knob == "fpu_reduction" else None

    @property
    def cand_c_puct(self):
        """The candidate's c_puct OVERRIDE. `None` == the shared `--c-puct`."""
        return self.value if self.knob == "c_puct" else None


#: ⭐ THE THREE PRIMARY CELLS. Each is n=800 games = 400 seat-balanced decks x 2
#: seatings, on ITS OWN fresh band, against the UNMODIFIED champion.
#: ⭐ BOX ASSIGNMENT IS **WHOLE CELLS PER BOX** (`G-HOST`), per the funding brief.
#: The realized local:laptop rate ratio is ~1.46:1 (`DESIGN.md` §6), so 2 local
#: + 1 laptop is the best balance a 3-cell / 2-box whole-cell split admits; the
#: residual ~2.1 h imbalance is DISCLOSED, not engineered away by sub-celling.
CELLS: tuple[CellSpec, ...] = (
    CellSpec("CELL_FPU02", "local", "fpu_reduction", 0.2,
             BANDS["CELL_FPU02"], 400,
             "⭐⭐ THE PRIMARY — the 2026-06-02 screen's OWN dose (+45.4 elo, "
             "z 1.85, never confirmed), re-asked of the CLASSICAL champion on "
             "the backend where the knob was previously unreachable."),
    CellSpec("CELL_FPU04", "local", "fpu_reduction", 0.4,
             BANDS["CELL_FPU04"], 400,
             "⭐ THE SECOND DOSE — the other never-confirmed screen (+31.4 elo, "
             "z 1.28). Two doses give a DIRECTION across the axis; ⛔ they are "
             "NOT a bracket and no interpolation between them is licensed."),
    CellSpec("CELL_CPUCT10", "laptop", "c_puct", 1.0,
             BANDS["CELL_CPUCT10"], 400,
             "⭐ THE EXPLORATION-CONSTANT CELL — champion c_puct is 1.5; this "
             "asks 1.0. ⛔⛔ IT IS ALSO THE TRIGGER: a null here RE-KILLS the "
             "conditional tau pair (READ_RULE §6), which is the funded "
             "conditionality."),
)


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"unknown cell {name!r}; known: {[c.name for c in CELLS]}")


def cells_of_box(role: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.role == role)


#: ⭐ THE CONDITIONAL tau PAIR — SPECIFIED, NOT BUILT (`READ_RULE.md` §6).
#: ⛔ These are NOT in `CELLS` and `run_cells.sh` cannot launch them. They exist
#: here so the trigger, the shape and the bands are FROZEN BEFORE any number of
#: this round exists, and cannot be reconstructed favourably afterwards.
TAU_PAIR_SPEC = {
    "trigger": "CELL_CPUCT10 moves >= 2 sigma (|z_M| >= 2.0) on its OWN "
               "realized SE, in EITHER direction, after passing every gate.",
    "if_not_triggered": "⛔ THE tau PAIR IS RE-KILLED AND NOT FUNDED. That is "
                        "the funded conditionality, pre-registered here.",
    "cells": {"CELL_TAU8": {"knob": "tau_p", "value": 8.0,
                            "band": "the next free id at trigger time — "
                                    "⛔ NOT reserved here"},
              "CELL_TAU12": {"knob": "tau_p", "value": 12.0,
                             "band": "the next free id at trigger time"}},
    "protocol": "IDENTICAL to this round's: n=800 deck-paired (400 decks x 2 "
                "seatings) vs the UNMODIFIED champion, fair PIMC k16x1376="
                "22016 both sides, fixed_v1 + R9, exact_k 2 marginalized, rust "
                "both sides, leaf a36d2e15a3b3d71d both sides, tie-arbiter OFF "
                "both sides, each cell on its OWN fresh band.",
    "plumbing": "⚠️ tau_p is ALREADY a candidate-reachable knob path-wise (it "
                "rides `champ_cfg_dict` like c_puct) — which means it has the "
                "SAME defect c_puct does: `--tau-p` moves BOTH SIDES. A tau "
                "round needs `--cand-tau-p` added to `cand_search` exactly as "
                "`--cand-c-puct` was. ⛔ NOT built here.",
}


# =========================================================================== #
# 2. ADDRESS RESOLUTION — IS-D1 (carried verbatim in construction)             #
# =========================================================================== #

MISSING = object()


def _dig(doc, dotted: str):
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


def resolve(docs: Mapping[str, Mapping], *addresses: str):
    """`(value, address)` — the FIRST address that answers, or `(MISSING, None)`.

    ⛔ EVERY gate prints the address that answered: IS-D1's defect was a precheck
    that read `config` off `summary.json` — which carries NO config block at all
    — got `{}`, failed closed on one conjunct and passed VACUOUSLY on another.

    ⚠️⚠️ **`MISSING` IS NOT `None`.** This round turns on that distinction more
    than any before it: `config.cand_search.fpu_reduction = null` is a POSITIVE
    statement ("the champion's legacy optimistic q=0") while an ABSENT key means
    the harness never resolved the knob. `resolve` therefore returns the
    sentinel, and no gate may collapse the two.
    """
    for addr in addresses:
        doc_name, _, path = addr.partition(":")
        doc = docs.get(doc_name)
        if doc is None:
            continue
        v = _dig(doc, path)
        if v is not MISSING:
            return v, addr
    return MISSING, None


def gate(gid: str, ok: bool, detail, addr: str | None = None, why: str = "") -> dict:
    """One gate's verdict record. ⛔ `ABSENT` is `FAIL`, so an unresolved value
    arrives here as `ok=False` with `address=None` — never as a skip."""
    return {"gate": gid, "ok": bool(ok), "detail": detail,
            "address": addr or "ABSENT (no address answered) — ABSENT is FAIL",
            "why": why}


# =========================================================================== #
# 3. REV / PROVENANCE — carried from phasegate (the IS-A1 fold)                #
# =========================================================================== #

def split_dirty(code_rev: str) -> tuple[str, bool]:
    """`(sha_part, had_dirty_marker)`. The marker is WHOLE-TREE scoped and is
    REPORTED, never fatal — `run_manifest.code_rev()` computes dirtiness over the
    whole tree and the main tree is perpetually dirty with measurement logs. The
    fatal, code-path-scoped verdict is `SRC_CLEAN.jsonl`'s."""
    s = (code_rev or "").strip()
    if s.lower().endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def is_hex40(s) -> bool:
    return (isinstance(s, str) and len(s) == 40
            and all(c in "0123456789abcdef" for c in s.lower()))


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """`(ok, why)` — does a manifest's short `code_rev` NAME `PINNED_SRC_REV`?

    Strip the whole-tree `-dirty` marker, then require a `>= MIN_REV_PREFIX`-hex
    PREFIX match against the 40-hex pin. ⛔ Identity only; cleanliness is
    `SRC_CLEAN.jsonl`'s question, because only that reading is scoped to the
    code paths."""
    if not code_rev or not isinstance(code_rev, str):
        return False, "code_rev ABSENT — ABSENT is FAIL"
    if not pinned or not isinstance(pinned, str):
        return False, "PINNED_SRC_REV ABSENT — ABSENT is FAIL"
    cr, dirty = split_dirty(code_rev)
    cr, pn = cr.lower(), pinned.strip().lower()
    note = ("; ⚠️ whole-tree `-dirty` marker present — INFORMATIONAL ONLY (the "
            "code-path verdict is SRC_CLEAN.jsonl's)" if dirty else "")
    if not is_hex40(pn):
        return False, f"PINNED_SRC_REV {pinned!r} is not a 40-hex sha{note}"
    if len(cr) < MIN_REV_PREFIX or any(c not in "0123456789abcdef" for c in cr):
        return False, f"code_rev {code_rev!r} is not >= {MIN_REV_PREFIX} hex chars{note}"
    if not pn.startswith(cr):
        return False, (f"code_rev {code_rev!r} is not a prefix of PINNED_SRC_REV "
                       f"{pinned!r}{note}")
    return True, f"code_rev {code_rev!r} names PINNED_SRC_REV {pinned!r}{note}"


def cross_box_rev_gate(revs_by_cell: Mapping, pins_by_role: Mapping) -> dict:
    """⭐ THE IS-A1 FOLD, carried unchanged. "Was this ONE round, at ONE rev,
    across BOTH boxes?" — ⛔ NEVER by comparing one box's emitted short rev to
    the other's.

      (1) **THE PINS AGREE.** Every role that published a `PINNED_SRC_REV` must
          publish the SAME 40-hex sha. A missing pin is FAIL.
      (2) **EVERY EMITTED REV CANONICALIZES TO THAT PIN** via `rev_matches`.

    ⚠️ A single-box round (and the §9 smoke) passes (1) trivially with one pin,
    which is correct: there is no cross-box proposition to check."""
    pins = {r: (p or "").strip().lower()
            for r, p in (pins_by_role or {}).items() if p}
    base = {"pins": pins, "revs": dict(revs_by_cell or {}), "canonicalized": {}}
    if not pins:
        return {**base, "ok": False, "distinct_pins": [],
                "why": ("no box published a PINNED_SRC_REV — ABSENT is FAIL. The "
                        "cross-box single-rev property cannot be established "
                        "without the pins, and IS-A1 forbids falling back to "
                        "comparing the emitted revs to each other.")}
    bad_pins = sorted(r for r, p in pins.items() if not is_hex40(p))
    distinct = sorted(set(pins.values()))
    if bad_pins:
        return {**base, "ok": False, "distinct_pins": distinct,
                "why": (f"box(es) {bad_pins} published a PINNED_SRC_REV that is "
                        "not a 40-hex sha — ABSENT-or-malformed is FAIL.")}
    if len(distinct) > 1:
        return {**base, "ok": False, "distinct_pins": distinct,
                "why": ("⛔ THE BOXES WERE AT DIFFERENT COMMITS: their "
                        f"PINNED_SRC_REV files disagree ({distinct}). This is a "
                        "mixed-rev round and the git-bundle sync exists to "
                        "prevent exactly it. ⚠️⚠️ IT IS THE PRIMARY RISK OF THIS "
                        "ROUND SPECIFICALLY: the fpu plumbing is PYTHON-ONLY, so "
                        "a box running the pre-fix source would silently serve a "
                        "knob-FREE candidate — champion-vs-champion — with a "
                        "healthy-looking wheel and a healthy-looking leaf hash. "
                        "⚠️ NOTE THIS IS THE PINS DISAGREEING, NOT THE SHORT "
                        "REVS — the short revs disagreeing is EXPECTED (IS-A1).")}
    pin = distinct[0]
    canon, bad = {}, []
    for name, rev in (revs_by_cell or {}).items():
        ok, why = rev_matches(rev, pin)
        canon[name] = {"code_rev": rev, "ok": ok, "why": why}
        if not ok:
            bad.append(f"{name}: {why}")
    return {**base, "ok": not bad, "distinct_pins": distinct, "pin": pin,
            "canonicalized": canon,
            "why": ("every cell's emitted code_rev canonicalizes to the ONE pin "
                    f"{pin} that every box published — short revs of different "
                    "lengths are expected and harmless (IS-A1)" if not bad else
                    "⛔ a cell's emitted code_rev does NOT name the shared pin: "
                    + "; ".join(bad))}


_HOST_ALIASES = {"laptop": ("laptop", "laptop-wsl", "laptop-pop", "pop-os", "pop"),
                 "local": ("doctor", "5800x", "desktop", "local")}


def host_matches_box(observed_host, role: str) -> tuple[bool, str]:
    """`G-HOST` — substring test on a NORMALISED hostname.
    ⚠️ `laptop`/`laptop-wsl`/`laptop-pop`/`pop-os` are ONE physical machine."""
    if not observed_host or not isinstance(observed_host, str):
        return False, "host ABSENT — ABSENT is FAIL"
    h = observed_host.strip().lower()
    for alias in _HOST_ALIASES.get(role, ()):
        if alias in h:
            return True, f"host {observed_host!r} matches box role {role!r} (via {alias!r})"
    # the local box is whatever is NOT the laptop — stated explicitly, because a
    # negative test that is not written down is a test nobody can audit
    if role == "local" and not any(a in h for a in _HOST_ALIASES["laptop"]):
        return True, f"host {observed_host!r} is not the laptop ⇒ treated as {role!r}"
    return False, f"host {observed_host!r} does not match box role {role!r}"


# =========================================================================== #
# 4. THE STATISTIC — `RECON`'s independent re-implementation                   #
# =========================================================================== #

def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}`. A record missing `seed`, `a_seat` or `diff` is
    DROPPED here and shows up as a short `n_paired` at `G-DECKS` — it is never
    silently defaulted to zero."""
    out: dict[int, dict[int, float]] = {}
    for r in records:
        if not isinstance(r, Mapping):
            continue
        s, a, d = r.get("seed"), r.get("a_seat"), r.get("diff")
        if s is None or a is None or d is None:
            continue
        out.setdefault(int(s), {})[int(a)] = float(d)
    return out


def per_deck_margins(records: Iterable[Mapping]) -> dict[int, float]:
    """`D(d) = (diff(d, a_seat=0) + diff(d, a_seat=1)) / 2`, over decks appearing
    in BOTH seatings. A deck missing a seating is DROPPED, never zero-filled
    (`READ_RULE.md` §1). `diff` is CANDIDATE minus OPPONENT in POINTS, so
    `D > 0` ⇒ the candidate won."""
    return {s: (v[0] + v[1]) / 2.0
            for s, v in sorted(_by_deck(records).items()) if 0 in v and 1 in v}


def paired_margin(records: Iterable[Mapping]):
    """`READ_RULE.md` §1's statistic, recomputed from the raw records.

    Returns `(mean, z, n_paired, se, per_deck_list)`. ⚠️ Accumulated with
    `math.fsum` rather than `sum` DELIBERATELY: the point of a witness is to be a
    DIFFERENT computation. An imported `_paired_z` would agree by construction
    and witness nothing. ⛔ It can only VOID, never move, a number."""
    per_deck = list(per_deck_margins(records).values())
    n = len(per_deck)
    if n < 2:
        return None, None, n, None, per_deck
    mean = math.fsum(per_deck) / n
    var = math.fsum((d - mean) ** 2 for d in per_deck) / (n - 1)
    se = math.sqrt(var / n)
    z = (mean / se) if se > 0 else float("nan")
    return mean, z, n, se, per_deck


def elo_sigma_unpaired(wr: float, n_games: int) -> float:
    """1σ on elo from the plain binomial, treating every GAME as independent.

    ⛔ THIS IS THE WRONG FOOTING FOR THIS ROUND and is emitted only so the
    correction is auditable: 800 games are 400 decks × 2 seatings, not 800
    independent draws."""
    return ((400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n_games)
            / (wr * (1 - wr)))


def elo_sigma_paired(wr: float, n_games: int) -> float:
    """⭐ 1σ on elo on the **DECK-PAIRED** footing — the one `BAR_ELO` is stated
    on, and the one the primary margin already uses. `PAIRING_FACTOR` applied."""
    return elo_sigma_unpaired(wr, n_games) * PAIRING_FACTOR


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from the raw records.

    ⚠️⚠️ **R4: THE EMITTED SIGMA IS DECK-PAIRED.** `elo_sig_1sigma_paired` is
    the field the read-out's CI is built from; `elo_sig_1sigma_unpaired` is
    carried beside it so the factor is visible rather than buried. ⛔ The old
    unlabelled `elo_sig_1sigma` key is GONE ON PURPOSE — a footing that is not
    in the field name is a footing nobody checks.

    ⚠️⚠️ THE ELO IS THIS ROUND'S **SECONDARY**, and it is in an awkward position:
    the FUNDING BRIEF states the bar in elo (`~±17.5 elo` at 2σ) because the
    PRIOR ART is in elo (`+45.4` / `+31.4`), but house doctrine is that the
    deck-paired MARGIN is the statistic and `elo` may never be quoted bare
    (`feedback_trend_beats_underpowered_steps`; Stage-2's own elo secondary did
    not convict at `+23.92`, CI `[−0.21, +48.06]`). `READ_RULE.md` §5 resolves
    it: the MARGIN carries the branch, the elo is reported BESIDE it with its
    own CI on every branch, and a disagreement between the two is DISCLOSED
    rather than arbitrated."""
    scored = [r for r in records if isinstance(r, Mapping) and "diff" in r]
    n = len(scored)
    if n == 0:
        return {"n": 0, "W": 0, "D": 0, "L": 0, "winrate": None, "elo": None,
                "elo_sig_1sigma_paired": None, "elo_sig_1sigma_unpaired": None,
                "elo_footing": "deck-paired", "avg_diff": None}
    w = sum(1 for r in scored if r.get("won_by_champ") is True)
    d = sum(1 for r in scored if r.get("drew") is True)
    wr = (w + 0.5 * d) / n
    if 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1.0 - wr))
        sig_u = elo_sigma_unpaired(wr, n)
        sig_p = sig_u * PAIRING_FACTOR
    else:
        elo, sig_u, sig_p = (math.copysign(800.0, wr - 0.5),
                             float("nan"), float("nan"))
    return {"n": n, "W": w, "D": d, "L": n - w - d, "winrate": wr, "elo": elo,
            "elo_sig_1sigma_paired": sig_p,
            "elo_sig_1sigma_unpaired": sig_u,
            "elo_footing": "deck-paired",
            "elo_pairing_factor": PAIRING_FACTOR,
            "avg_diff": math.fsum(float(r["diff"]) for r in scored) / n}


def recon_close(a, b) -> bool:
    """`RECON` tolerance: rel 1e-6 / abs 1e-9. `None` closes only to `None` — an
    absent field must witness ABSENT, not merely small."""
    if a is None or b is None:
        return a is None and b is None
    try:
        af, bf = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(af) and math.isnan(bf):
        return True
    return abs(af - bf) <= max(RECON_ATOL, RECON_RTOL * max(abs(af), abs(bf)))


def se_model(n_decks: int) -> float:
    """`SIGMA_D_MODEL / sqrt(n)`. 400 decks -> 0.6905. ⛔ POWER ARITHMETIC ONLY —
    never a denominator in a branch test."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    """Print realized vs modelled SE and FLAG a ratio outside `SE_ANOMALY_BAND`.
    ⛔ Reported, NEVER a branch input."""
    modelled = se_model(n_decks)
    if realized_se is None or modelled <= 0:
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True,
                "note": "SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": not (lo <= ratio <= hi),
            "direction": ("TIGHTER than modelled" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)"
                          if ratio > hi else "inside the band"),
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def power_at(delta: float, se: float, bar: float = BAR_M) -> float:
    """P(the cell fires `F-RESURRECT`) at a true effect `delta`.

    ⚠️ STATED HONESTLY: at n=400 decks a TRUE `+1.381` (== `BAR_M`) gives
    `z = 2.00` — **50% power**. What the `n` guarantees is the BOUNDING
    direction: `F-REKILL` returns a real 95% upper bound, and on this axis the
    bounding direction is the decision-relevant one (`docs/LEVER_INDEX.md`
    already records FPU as CLOSED, so the question this round can actually
    settle is whether the reopening survives)."""
    if se is None or se <= 0:
        return float("nan")
    thresh = max(bar, BRANCH_Z * se)
    return 1.0 - _phi((thresh - delta) / se)


# =========================================================================== #
# 5. THE BRANCH LADDER — `READ_RULE.md` §5, pre-registered and EXHAUSTIVE      #
# =========================================================================== #

BRANCHES = ("U-VOID-INSTRUMENT", "F-NEGATIVE", "F-RESURRECT", "F-REKILL",
            "F-UNRESOLVED")


def branch_for_cell(M, se, z, *, gates_ok: bool) -> str:
    """The §5 ladder, IN ORDER. First match wins. Adjudicated PER CELL on that
    cell's OWN realized SE, AGAINST ZERO.

    ⛔ Exclusive and exhaustive BY CONSTRUCTION, and ORDERED rather than
    disjoint: `F-NEGATIVE` requires `M <= 0 ∧ z <= -2`, which forces
    `UB95 = M + 2SE <= 0 < BAR_M`, so it would ALSO satisfy `F-REKILL` — which
    is exactly why it is checked first.
    """
    if not gates_ok:
        return "U-VOID-INSTRUMENT"
    if M is None or se is None or z is None:
        return "U-VOID-INSTRUMENT"
    ub95 = M + 2.0 * se
    if M <= 0.0 and z <= -BRANCH_Z:
        return "F-NEGATIVE"
    if M >= BAR_M and z >= BRANCH_Z:
        return "F-RESURRECT"
    if ub95 < BAR_M:
        return "F-REKILL"
    return "F-UNRESOLVED"


def branch_grid(step: float = 0.05, se_values=(0.3, 0.5, 0.691, 0.9, 1.4)) -> dict:
    """⭐ `READ_RULE.md` §5's own demand: sweep a dense `(M, SE)` grid and prove
    EXACTLY ONE branch fires at every point, and that every branch is REACHABLE
    (§4.1's "no branch is unreachable by construction")."""
    seen: dict[str, int] = {}
    m = -8.0
    pts = 0
    while m <= 8.0 + 1e-9:
        for se in se_values:
            z = m / se
            b = branch_for_cell(m, se, z, gates_ok=True)
            seen[b] = seen.get(b, 0) + 1
            pts += 1
        m += step
    return {"points": pts, "histogram": seen, "reachable": sorted(seen),
            "all_reachable": set(seen) >= {"F-NEGATIVE", "F-RESURRECT",
                                           "F-REKILL", "F-UNRESOLVED"}}


def tau_trigger(cpuct_cell: Mapping | None) -> dict:
    """⭐⭐ `READ_RULE.md` §6 — THE FUNDED CONDITIONALITY, evaluated in code so
    it cannot be re-read favourably after the fact.

    The tau pair is funded **iff** `CELL_CPUCT10` passed every gate AND moved
    `>= 2 sigma` in EITHER direction on its own realized SE. Anything else —
    including `F-REKILL` and `F-UNRESOLVED` — **RE-KILLS tau**."""
    if not cpuct_cell:
        return {"triggered": False, "z": None,
                "why": "⛔ CELL_CPUCT10 is ABSENT — ABSENT is FAIL, and a tau "
                       "pair cannot be triggered by a cell that does not exist."}
    if not cpuct_cell.get("gates_ok"):
        return {"triggered": False, "z": cpuct_cell.get("stats", {}).get("z"),
                "why": "⛔ CELL_CPUCT10 is U-VOID-INSTRUMENT — a voided cell "
                       "triggers nothing. ⚠️ It also does NOT re-kill tau: a "
                       "broken instrument is not a null. The correct action is "
                       "to re-run the cell, and that is an OWNER decision."}
    z = cpuct_cell.get("stats", {}).get("z")
    if z is None:
        return {"triggered": False, "z": None,
                "why": "⛔ no z — ABSENT is FAIL"}
    fired = abs(float(z)) >= BRANCH_Z
    return {
        "triggered": bool(fired), "z": float(z), "bar": BRANCH_Z,
        "why": (f"⭐ CELL_CPUCT10 moved |z| = {abs(float(z)):.3f} >= {BRANCH_Z} — "
                "the tau pair {8, 12} IS TRIGGERED and its spec is "
                "screen_lib.TAU_PAIR_SPEC. ⚠️ Triggered is NOT funded: the owner "
                "funds it, and the plumbing note in that spec (--cand-tau-p does "
                "not exist yet) is a build item, not a launch."
                if fired else
                f"⛔ CELL_CPUCT10 moved |z| = {abs(float(z)):.3f} < {BRANCH_Z}. "
                "⭐⭐ THE tau PAIR IS RE-KILLED AND NOT FUNDED — that is this "
                "round's funded conditionality, pre-registered before game 1. "
                "⚠️ 'Re-killed' means UNFUNDED, not 'proven worthless': a "
                "|z| < 2 cell is a bound, and feedback_noisy_plateau_not_a_"
                "conclusion binds on any stronger reading."),
    }


RIDERS_ALWAYS = (
    "⛔⛔ docs/LEVER_INDEX.md:146 RECORDS THIS AXIS AS CLOSED ('M3 later ran the "
    "full curve -> peaks at parity, axis CLOSED'). This round is a deliberate "
    "REOPENING, and the reopening argument is NARROW: every prior FPU cell "
    "measured a NEURAL or VALUE-BLENDED agent, and NONE of them could have "
    "measured the classical champion, because the knob was structurally "
    "unreachable on the champion's backend until 2026-08-29 (rust_agent."
    "search_config_rs passed a hard-coded None). The prior evidence is not "
    "wrong; it is about a different agent.",
    "⛔ The prior-art figures (+45.4 / +31.4 elo at n=200; the M3 curve peaking "
    "at parity) are CONTEXT ONLY — never pooled, never z-combined, never a gate "
    "input. They are CROSS-ERA as well as cross-band, which is strictly worse "
    "than the 1.8-2.2x cross-band over-dispersion CL-068 measured.",
    "⛔ Nothing here is a bracket. Two fpu doses give a DIRECTION; they do not "
    "locate an optimum and no interpolation between 0.2 and 0.4 is licensed "
    "(feedback_bracket_hyperparams: a peak at a ladder ENDPOINT is not "
    "bracketed, and two points are not a ladder).",
    "⛔ THREE CELLS ARE THREE COMPARISONS. At the 2-sigma bar the family-wise "
    "false-fire rate under a global null is ~3 x 2.3% ~= 7%. No correction is "
    "applied — the bars are pre-registered and each cell is its own question — "
    "but the inflation is DISCLOSED on every branch, and a LONE firing cell "
    "beside two nulls is read as feedback_results_table_source_of_truth's NOISE "
    "SIGNATURE, not as a peak.",
    "⛔ governance/PRODUCTION.yaml is UNTOUCHED on every branch. No branch "
    "licenses a production change of any kind.",
    "⚠️ elo may never be quoted bare. The deck-paired MARGIN carries every "
    "branch; the elo is reported beside it with its own CI, and a disagreement "
    "between the two is DISCLOSED rather than arbitrated.",
)
RIDERS_F_RESURRECT = (
    "⭐⭐ F-RESURRECT is a claim about THE KNOB ON THE CLASSICAL CHAMPION AT "
    "k16x1376, ON THIS BAND, AT THIS DOSE. It is NOT a claim that the "
    "2026-06-02 screens replicate — those were a neural agent at sims=200 and "
    "no cross-era comparison is licensed.",
    "⛔ IT DOES NOT LICENSE A PRODUCTION CHANGE. A single 2-sigma cell on a "
    "fresh band is one cell; feedback_results_table_source_of_truth requires a "
    "confirm before promotion, on a band that has not influenced a decision.",
    "⛔ It says nothing about the OTHER dose or about tau. Each cell is its own "
    "question.",
    "⚠️ It is a k16x1376 result. FPU acts per determinization tree and "
    "sims_per_det is unchanged from the 11008 era, so the MECHANISM transfers "
    "downward in k — but that is an ARGUMENT, not a measurement.",
)
RIDERS_F_REKILL = (
    "⚠️ F-REKILL BOUNDS; IT DOES NOT ZERO. The reading is 'below the round's own "
    "2-sigma resolution at 95%', never 'FPU is worthless'.",
    "⭐ It DOES discharge the funded decision: on this evidence the never-"
    "confirmed 2026-06-02 screens do not reappear as a usable lever on the "
    "classical champion, docs/LEVER_INDEX.md:146's CLOSED verdict stands, and "
    "the row is updated to say the reopening was measured and failed.",
    "⚠️ It is a bound at THIS DOSE and THIS BUDGET. A different dose could "
    "clear the bar; this round measures two and no interpolation is licensed.",
)
RIDERS_F_NEGATIVE = (
    "⭐ F-NEGATIVE is the STRONGEST outcome available here and is fully "
    "pre-registered: a pessimistic FPU narrowing a search that is already "
    "well-tuned is a plausible harm, and the M3 curve's roll-off past 0.6 is "
    "consistent with it.",
    "⛔ It still does not license a production change (the champion already "
    "runs fpu=None — there is nothing to turn off).",
)
RIDERS_F_UNRESOLVED = (
    "⛔ F-UNRESOLVED IS NOT A NULL. feedback_noisy_plateau_not_a_conclusion "
    "binds: a flat read at z~1 does not prove dead, and this cell did not "
    "resolve its own bar in either direction.",
    "⚠️ On CELL_CPUCT10 specifically, F-UNRESOLVED still RE-KILLS the tau pair "
    "(READ_RULE §6) — the trigger is |z| >= 2, and 'unresolved' does not meet "
    "it. That is a FUNDING decision, not a scientific one.",
)


# =========================================================================== #
# 6. THE ROUND-SPECIFIC GATES                                                  #
# =========================================================================== #

def decks_gate(spec: CellSpec, records: Sequence[Mapping],
               all_specs: Sequence[CellSpec] = CELLS) -> dict:
    """⛔ `G-DECKS` — **REWRITTEN AGAIN, AND IN THE OPPOSITE DIRECTION** from
    phasegate, whose ranges OVERLAPPED by design (one deck set, decomposed).

    ⭐ THIS ROUND'S THREE CELLS SIT ON THREE SEPARATE BANDS. Nothing is pooled,
    nothing is deck-matched across cells, and DISJOINTNESS is therefore an
    assertable property again — a copied phasegate clause would have skipped it
    and a copied invasion-r3 clause would have been right by accident.

    What IS asserted:
      (a) every realized seed lies inside **this cell's own** range;
      (b) no deck appears at one seat only (a half-played deck is DROPPED from
          the statistic and must SURFACE here, never be zero-filled);
      (c) `n_common` equals the cell's frozen `n_decks`;
      (d) ⭐ this cell's range does not intersect ANY other cell's.
    """
    by_deck = _by_deck(records)
    seeds = sorted(by_deck)
    lo, hi = spec.seed_start, spec.seed_end
    out_of_range = [s for s in seeds if not (lo <= s <= hi)]
    half = sorted(s for s, v in by_deck.items() if not (0 in v and 1 in v))
    n_common = len(per_deck_margins(records))
    clashes = [c.name for c in all_specs
               if c.name != spec.name
               and not (c.seed_end < lo or c.seed_start > hi)]
    ok = (not out_of_range and not half and n_common == spec.n_decks
          and not clashes)
    return gate(
        "G-DECKS", ok,
        {"range": [lo, hi], "n_seeds": len(seeds), "n_common": n_common,
         "frozen_n_decks": spec.n_decks, "out_of_range": out_of_range[:20],
         "half_played_decks": half[:20], "range_clashes": clashes,
         "all_cell_ranges": [[c.seed_start, c.seed_end, c.name]
                             for c in all_specs]},
        "raw seed*_a*.json",
        ("every realized seed is inside this cell's own range, both seatings are "
         "present on every deck, n_common == the frozen n, and this cell's band "
         "does not intersect any other cell's" if ok else
         "⛔ G-DECKS FAILED: " + "; ".join(filter(None, [
             f"{len(out_of_range)} seed(s) outside [{lo},{hi}]" if out_of_range else "",
             f"{len(half)} deck(s) played at ONE seat only" if half else "",
             (f"n_common {n_common} != frozen {spec.n_decks}"
              if n_common != spec.n_decks else ""),
             f"band range intersects {clashes}" if clashes else "",
         ]))))


def leaf_gate(cand_hash, opp_hash, cand_curve) -> dict:
    """`G-LEAF` — ⭐ BOTH SIDES EQUAL, and equal to `a36d2e15a3b3d71d`.

    Neither knob in this round is a leaf term: `fpu_reduction` is read on the
    PUCT descent and `c_puct` scales the exploration bonus. They move NO leaf
    hash — which is precisely why a moved-hash check can never prove this
    surface LIVE, and why `G-FPU` / `G-CPUCT` / `G-TWOSIDED` exist."""
    same = (cand_hash is not None and cand_hash == opp_hash)
    right = cand_hash == LEAF_HASH
    curve_ok = list(cand_curve or []) == LEAF_CURVE125
    ok = same and right and curve_ok
    return gate("G-LEAF", ok,
                {"cand_leaf_hash": cand_hash, "opp_leaf_hash": opp_hash,
                 "expected": LEAF_HASH, "cand_curve": cand_curve},
                "manifest:config.{cand,opp}_leaf_hash",
                ("both sides carry the SAME leaf a36d2e15a3b3d71d (curve125) — "
                 "neither knob is a leaf term" if ok else
                 "⛔ G-LEAF FAILED: " + "; ".join(filter(None, [
                     "the two sides' leaf hashes DIFFER (misconfigured cell — "
                     "neither knob moves a leaf hash)" if not same else "",
                     f"leaf hash is not {LEAF_HASH}" if not right else "",
                     "v29_meeple_curve is not curve125" if not curve_ok else "",
                 ]))))


#: `G-SINGLEVAR`'s alias table. ⚠️ PER CELL: the knob the cell OWNS is asserted
#: DIFFERENT, every other alias is asserted EQUAL. `fpu_reduction` is in the
#: table because a champion that silently carried one would be the same defect
#: class in mirror image.
SINGLEVAR_ALIASES = ("k_dets", "sims_per_det", "total_sims", "c_puct", "tau_p",
                     "value_norm", "leaf_quantize", "final_select",
                     "fpu_reduction")


def singlevar_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """`G-SINGLEVAR` — ⛔ **REWRITTEN, NOT COPIED.**

    Phasegate could demand every search knob be equal because its variable lived
    in a separate container. ⭐ HERE THE VARIABLE **IS** A SEARCH KNOB. On
    `CELL_CPUCT10` the candidate's `c_puct` MUST DIFFER from the opponent's —
    an unedited copy of phasegate's clause would VOID the very cell it was
    written to protect. So:

      * the alias the cell OWNS  -> asserted **DIFFERENT**, and equal to the
        cell's frozen value on the candidate side;
      * every OTHER alias        -> asserted **EQUAL**.

    `rows` is `{alias: {"champion": v, "opponent": v, "addresses": [...]}}`.
    """
    owned = spec.knob
    bad, notes = [], []
    for alias in SINGLEVAR_ALIASES:
        r = rows.get(alias) or {}
        cv, ov = r.get("champion"), r.get("opponent")
        present = ("champion" in r and "opponent" in r
                   and not r.get("champion_absent") and not r.get("opponent_absent"))
        if not present:
            bad.append(f"{alias} ABSENT on one side")
            continue
        if alias == owned:
            if repr(cv) == repr(ov):
                bad.append(f"⛔ {alias}: the cell's OWN knob is IDENTICAL on both "
                           f"sides ({cv!r}) — this cell is champion-vs-champion")
            elif float(cv) != float(spec.value):
                bad.append(f"{alias}: candidate {cv!r} != this cell's frozen "
                           f"{spec.value!r}")
            else:
                notes.append(f"⭐ {alias}: candidate {cv!r} vs opponent {ov!r} — "
                             "the SINGLE VARIABLE, differing as frozen")
        elif repr(cv) != repr(ov):
            bad.append(f"{alias}: champion {cv!r} vs opponent {ov!r} — a SECOND "
                       "variable; this cell is not single-variable")
    return gate("G-SINGLEVAR", not bad,
                {"owned_alias": owned, "frozen_value": spec.value,
                 "rows": dict(rows), "notes": notes},
                "manifest:config.champion.* vs config.opponent.champ_cfg.*",
                ("; ".join(notes) + " — every OTHER alias is identical across the "
                 "two sides" if not bad else
                 "⛔ G-SINGLEVAR FAILED: " + "; ".join(bad)))


def knob_gate(spec: CellSpec, requested_fpu, requested_c, fpu_addr, c_addr,
              shared_c) -> dict:
    """⭐⭐ `G-FPU` / `G-CPUCT` — THE INVERTED-LIVENESS GATE, on the REQUEST side.

    ⛔⛔ **THIS IS THE GATE THE WHOLE ROUND EXISTS BEHIND.** Until 2026-08-29
    `rust_agent.search_config_rs` passed a HARD-CODED `None` into
    `SearchConfigRs`'s `fpu_reduction` slot: a cell run over that defect plays
    champion-vs-champion, moves no leaf hash, produces a perfectly healthy
    winrate inside `G-SAT`'s rail, and reads as a clean, credible null. Every
    other gate in this file would have passed it.

    ⚠️ `MISSING` IS NOT `None`. `config.cand_search.fpu_reduction = null` is a
    POSITIVE statement ("the champion's legacy optimistic q=0"); an ABSENT key
    means a harness that never resolved the knob, and ABSENT is FAIL.

    ⚠️ This gate reads the REQUEST (`config.cand_search`, written from the CLI).
    `G-TWOSIDED` reads the two sides' RESOLVED configs. Both are required: a
    request that never bound and a binding nobody asked for are different bugs.
    """
    want_fpu, want_c = spec.cand_fpu, spec.cand_c_puct
    bad = []
    if requested_fpu is MISSING:
        bad.append("config.cand_search.fpu_reduction ABSENT — ABSENT is FAIL. A "
                   "harness predating measurement/fpu_resurrection_prep cannot "
                   "be adjudicated: its candidate was fpu-BLIND by construction.")
    elif (requested_fpu is None) != (want_fpu is None) or (
            want_fpu is not None and float(requested_fpu) != float(want_fpu)):
        bad.append(f"fpu_reduction is {requested_fpu!r}, this cell is frozen at "
                   f"{want_fpu!r}")
    if requested_c is MISSING:
        bad.append("config.cand_search.c_puct ABSENT — ABSENT is FAIL")
    elif (requested_c is None) != (want_c is None) or (
            want_c is not None and float(requested_c) != float(want_c)):
        bad.append(f"c_puct override is {requested_c!r}, this cell is frozen at "
                   f"{want_c!r}")
    if want_c is None and shared_c is not MISSING and requested_c is None:
        pass          # correct: the candidate rides the shared --c-puct
    gid = "G-FPU" if spec.knob == "fpu_reduction" else "G-CPUCT"
    return gate(gid, not bad,
                {"requested_fpu_reduction": (None if requested_fpu is MISSING
                                             else requested_fpu),
                 "fpu_absent": requested_fpu is MISSING,
                 "requested_c_puct_override": (None if requested_c is MISSING
                                               else requested_c),
                 "c_puct_absent": requested_c is MISSING,
                 "shared_c_puct": (None if shared_c is MISSING else shared_c),
                 "frozen": {"fpu_reduction": want_fpu, "c_puct": want_c},
                 "addresses": {"fpu": fpu_addr, "c_puct": c_addr}},
                fpu_addr or c_addr,
                (f"the REQUEST matches this cell's frozen knob "
                 f"(fpu={want_fpu!r}, c_puct override={want_c!r})" if not bad
                 else f"⛔ {gid} FAILED: " + "; ".join(bad)))


def twosided_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """⭐⭐ `G-TWOSIDED` — THE SECOND, INDEPENDENT WITNESS.

    `G-FPU` proves the knob was REQUESTED. This proves it BOUND, and bound ON
    THE CANDIDATE ONLY — read off the two sides' RESOLVED `HeuristicPriorConfig`
    blocks rather than off the flag that asked for it. It is this round's
    analogue of phasegate's `G-PHI`, which had per-ply fire counters to read; a
    PUCT constant has no fire counter, so the resolved-config comparison is the
    strongest play-adjacent witness available, and `DESIGN.md` §7.2 says so
    plainly rather than overclaiming it.

    ⛔ ABSENT is FAIL on BOTH sides. `config.opponent.champ_cfg.fpu_reduction`
    is emitted as an explicit `null` precisely so this gate has an address to
    read instead of an exception to make.
    """
    bad, seen = [], {}
    for alias, want_cand in (("fpu_reduction", spec.cand_fpu),
                             ("c_puct", spec.cand_c_puct)):
        r = rows.get(alias) or {}
        cv, ov = r.get("champion"), r.get("opponent")
        seen[alias] = {"candidate": cv, "opponent": ov}
        if r.get("champion_absent"):
            bad.append(f"config.champion.{alias} ABSENT — ABSENT is FAIL")
            continue
        if r.get("opponent_absent"):
            bad.append(f"config.opponent.champ_cfg.{alias} ABSENT — ABSENT is "
                       "FAIL (the opponent must state its value POSITIVELY, "
                       "which is why the harness emits an explicit null)")
            continue
        if alias == "fpu_reduction":
            if ov is not None:
                bad.append(f"⛔ the OPPONENT carries fpu_reduction={ov!r} — it is "
                           "not the unmodified champion")
            if want_cand is None and cv is not None:
                bad.append(f"the candidate carries fpu_reduction={cv!r} on a cell "
                           "frozen without one")
            if want_cand is not None and (cv is None
                                          or float(cv) != float(want_cand)):
                bad.append(f"⛔⛔ the candidate's RESOLVED fpu_reduction is {cv!r}, "
                           f"not the frozen {want_cand!r} — the knob did NOT bind. "
                           "This is exactly the hard-coded-None defect this round "
                           "was funded to close, and a cell over it is "
                           "champion-vs-champion.")
        else:                                    # c_puct
            if want_cand is None:
                if cv is None or ov is None or float(cv) != float(ov):
                    bad.append(f"c_puct differs across the sides ({cv!r} vs "
                               f"{ov!r}) on a cell that froze no override")
            else:
                if cv is None or float(cv) != float(want_cand):
                    bad.append(f"the candidate's RESOLVED c_puct is {cv!r}, not "
                               f"the frozen {want_cand!r}")
                if ov is not None and float(ov) == float(want_cand):
                    bad.append("⛔ the OPPONENT's c_puct MOVED TOO — this is the "
                               "`--c-puct` trap: the shared flag builds BOTH "
                               "sides, so a cell built on it is "
                               "champion-vs-champion. Only --cand-c-puct is "
                               "candidate-only.")
    return gate("G-TWOSIDED", not bad, {"resolved": seen, "cell_knob": spec.knob,
                                        "frozen_value": spec.value},
                "manifest:config.champion.* vs config.opponent.champ_cfg.*",
                ("⭐ the knob BOUND on the candidate's resolved config and the "
                 "opponent carries the champion's values" if not bad else
                 "⛔ G-TWOSIDED FAILED: " + "; ".join(bad)))


def arb_off_gate(cell_manifest: Mapping) -> dict:
    """`G-ARB-OFF` — the tie arbiter is OFF on BOTH sides (single-variable
    discipline). ⚠️ `PRODUCTION.yaml` has carried `B=64` since 2026-08-20, so
    "off" is a DEVIATION FROM THE DEPLOYED CHAMPION and `DESIGN.md` §2.3 owes
    the reason: the arbiter is a stochastic post-search hook whose fires would
    add variance orthogonal to the knob under test, on BOTH sides. The price is
    that the answer is about the arbiter-free champion, and that price rides on
    every branch.

    ⚠️ Scan CONTAINER segments for a stray armed block, but read TERMINAL
    `*.tiearb_enabled` values — a healthy archive emits terminal `false` on both
    sides (the phasegate `G-TIEARB-ARM` shape, inverted)."""
    armed, containers = [], []

    def walk(node, path):
        if isinstance(node, Mapping):
            for k, v in node.items():
                p = f"{path}.{k}" if path else k
                if isinstance(v, Mapping):
                    if k.endswith("tiearb"):
                        containers.append(p)
                        if v.get("enabled") is True:
                            armed.append(p)
                    walk(v, p)
                elif k == "tiearb_enabled" and v is True:
                    armed.append(p)
    walk(cell_manifest or {}, "")
    ok = not armed and bool(cell_manifest)
    return gate("G-ARB-OFF", ok,
                {"armed": armed, "tiearb_containers": containers},
                "manifest (full walk)",
                ("the tie arbiter is DISABLED on both sides — the cell's knob is "
                 "the only moving part. ⚠️ This DEVIATES from the deployed "
                 "champion (PRODUCTION.yaml carries B=64 since 2026-08-20); the "
                 "price rides on every branch (DESIGN §2.3)." if ok else
                 f"⛔ G-ARB-OFF FAILED: an arbiter is ARMED at {armed} — the cell "
                 "has two moving parts and is not single-variable"))


# =========================================================================== #
# 7. SELF-CHECK — the library's own invariants                                 #
# =========================================================================== #

def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean.
    ⛔ Run by `analyze_fpu.py --selftest` AND by `run_cells.sh`'s precondition
    ladder; a non-empty list is a BUILD failure, not a round failure."""
    p: list[str] = []
    # the cells
    if len(CELLS) != 3:
        p.append(f"CELLS has {len(CELLS)} entries, the round is THREE cells")
    if {c.name for c in CELLS} != set(BANDS):
        p.append("CELLS' names do not match BANDS' keys")
    for c in CELLS:
        if c.seed_start != BANDS[c.name]:
            p.append(f"{c.name} does not start at its own band {BANDS[c.name]}")
        if c.n_decks != 400 or c.n_games != 800:
            p.append(f"{c.name} is {c.n_decks} decks / {c.n_games} games, "
                     "the funded shape is 400 decks / 800 games")
        if c.knob not in ("fpu_reduction", "c_puct"):
            p.append(f"{c.name} owns an unknown knob {c.knob!r}")
        if (c.cand_fpu is None) == (c.cand_c_puct is None):
            p.append(f"{c.name} must own EXACTLY ONE knob")
    # ⭐ the disjointness the round rests on
    rng = sorted((c.seed_start, c.seed_end, c.name) for c in CELLS)
    for a, b in zip(rng, rng[1:]):
        if b[0] <= a[1]:
            p.append(f"cell ranges INTERSECT: {a} and {b}")
    # ⛔ no cell's range may touch the throwaway block the smoke plays: a smoke
    # deck landing inside a real cell's range would put an un-adjudicated,
    # pre-launch-commit archive on a claimed band.
    t_lo, t_hi = THROWAWAY_BASE, THROWAWAY_BASE + THROWAWAY_SPAN - 1
    for c in CELLS:
        if not (c.seed_end < t_lo or c.seed_start > t_hi):
            p.append(f"{c.name}'s range intersects the THROWAWAY block "
                     f"[{t_lo},{t_hi}]")
    # box assignment: whole cells per box, both boxes used
    if {c.role for c in CELLS} != {"local", "laptop"}:
        p.append("the round does not use both boxes")
    # the budget
    if K_DETS * SIMS_PER_DET != TOTAL_SIMS:
        p.append(f"{K_DETS} x {SIMS_PER_DET} != {TOTAL_SIMS}")
    if (K_DETS, SIMS_PER_DET, TOTAL_SIMS) != (16, 1376, 22016):
        p.append("the budget is not the 2026-08-30 promoted champion k16x1376")
    # the sizing arithmetic DESIGN §3 states
    if abs(se_model(400) - 0.6905) > 5e-4:
        p.append(f"se_model(400) = {se_model(400):.4f}, DESIGN §3 says 0.6905")
    if abs(BAR_M - 2 * se_model(400)) > 2e-3:
        p.append(f"BAR_M {BAR_M} is not the 2-sigma resolution "
                 f"{2 * se_model(400):.4f} at n=400 decks")
    # ⭐ R4 — BAR_ELO's PROVENANCE ASSERT, the exact twin of BAR_M's above.
    # `BAR_ELO` is the DECK-PAIRED 2σ at wr=0.5 over 800 games (400 decks x 2
    # seatings). Deriving it here means the constant and the emitted sigma can
    # never again sit on different footings without this file failing to build.
    bar_elo_paired = 2.0 * elo_sigma_paired(0.5, 800)
    if abs(BAR_ELO - bar_elo_paired) > 0.05:
        p.append(f"BAR_ELO {BAR_ELO} is not the DECK-PAIRED 2-sigma resolution "
                 f"{bar_elo_paired:.4f} at 800 games / 400 decks (the UNPAIRED "
                 f"figure is {2 * elo_sigma_unpaired(0.5, 800):.4f} — that is "
                 "the mismatch R4 fixed)")
    if abs(PAIRING_FACTOR - 0.7071) > 1e-4:
        p.append(f"PAIRING_FACTOR {PAIRING_FACTOR} is not 1/sqrt(2)")
    # ⛔ elo is NEVER a branch input — asserted, not assumed.
    if "elo" in branch_for_cell.__code__.co_varnames:
        p.append("branch_for_cell has taken an elo argument — elo may NEVER be "
                 "a branch input (READ_RULE §1.1)")
    pw = power_at(BAR_M, se_model(400))
    if not (0.48 <= pw <= 0.52):
        p.append(f"power at a TRUE +{BAR_M} and n=400 is {pw:.3f}; DESIGN §3 "
                 "says ~50%")
    # the ladder
    g = branch_grid()
    if not g["all_reachable"]:
        p.append(f"not every §5 branch is reachable: {g['reachable']}")
    if branch_for_cell(0.0, 0.7, 0.0, gates_ok=False) != "U-VOID-INSTRUMENT":
        p.append("a failed gate does not void first")
    if branch_for_cell(-2.0, 0.7, -2.9, gates_ok=True) != "F-NEGATIVE":
        p.append("F-NEGATIVE is not checked before F-REKILL")
    if branch_for_cell(0.0, 0.5, 0.0, gates_ok=True) != "F-REKILL":
        p.append("a tight null does not read F-REKILL")
    if branch_for_cell(0.0, 1.4, 0.0, gates_ok=True) != "F-UNRESOLVED":
        p.append("a WIDE null does not read F-UNRESOLVED — it must not read REKILL")
    if branch_for_cell(2.5, 0.7, 3.6, gates_ok=True) != "F-RESURRECT":
        p.append("a clear positive does not read F-RESURRECT")
    # ⭐ the bar must not be clearable by an effect the design cannot resolve
    if branch_for_cell(BAR_M - 0.01, 0.69, (BAR_M - 0.01) / 0.69,
                       gates_ok=True) == "F-RESURRECT":
        p.append("an effect BELOW BAR_M fired F-RESURRECT")
    # the tau conditionality
    if tau_trigger({"gates_ok": True, "stats": {"z": 1.2}})["triggered"]:
        p.append("a |z|<2 CELL_CPUCT10 triggered the tau pair")
    if not tau_trigger({"gates_ok": True, "stats": {"z": -2.4}})["triggered"]:
        p.append("a NEGATIVE 2-sigma CELL_CPUCT10 did not trigger tau (the "
                 "trigger is |z|, in EITHER direction)")
    if tau_trigger({"gates_ok": False, "stats": {"z": 9.0}})["triggered"]:
        p.append("a VOIDED CELL_CPUCT10 triggered the tau pair")
    if tau_trigger(None)["triggered"]:
        p.append("an ABSENT CELL_CPUCT10 triggered the tau pair")
    return p


if __name__ == "__main__":                                    # pragma: no cover
    probs = sanity_check()
    print(json.dumps({"sanity_problems": probs,
                      "cells": [{"name": c.name, "role": c.role, "knob": c.knob,
                                 "value": c.value, "band": c.seed_start,
                                 "n_games": c.n_games} for c in CELLS],
                      "budget": [K_DETS, SIMS_PER_DET, TOTAL_SIMS],
                      "bars": {"BAR_M": BAR_M, "BAR_ELO": BAR_ELO,
                               "BRANCH_Z": BRANCH_Z},
                      "branch_grid": branch_grid()}, indent=2))
    raise SystemExit(1 if probs else 0)
