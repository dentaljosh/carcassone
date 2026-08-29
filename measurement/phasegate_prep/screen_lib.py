#!/usr/bin/env python3
"""`screen_lib` — the PHASE-GATE round's shared instrument library.

⭐ **A FORK of `measurement/invasion_screen_r3_prep/screen_lib.py`**, carrying the
hardened parts verbatim in construction (`cross_box_rev_gate` — the IS-A1 fold —
`rev_matches`, `is_hex40`, `paired_margin`, `winrate_elo`, `recon_close`) and
REWRITING the parts that are round-specific. `DESIGN.md` §7.6 names the fork and
names the two gates that must NOT be copied:

  ⛔ **`G-DECKS` — REWRITTEN.** Invasion r3's cells had DISJOINT deck ranges and
     its gate asserted disjointness. ⭐ THIS ROUND'S RANGES **OVERLAP BY DESIGN**
     (`DESIGN.md` §5): `ARB_FULL`'s 400 decks are a SUBSET of `ARB_EARLY`'s
     1,200, because a decomposition wants ONE deck set and `FULL − EARLY` is a
     deck-paired companion. An unedited copy of r3's clause would VOID EVERY
     HEALTHY CELL.
  ⛔ **`G-LEAF` — REWRITTEN.** In invasion r3 the two sides' leaf hashes DIFFER
     by design (the candidate carries the invasion term). ⭐ HERE THEY MUST BE
     EQUAL: the arbiter is a post-search ROOT hook, not a leaf term, so a cell
     whose two leaf hashes differ is MISCONFIGURED and voids.
  ⭐ **`G-SUBPOOL` — NEW.** `ARB_EARLY` is run as two same-config sub-cells on
     disjoint deck sub-ranges of one band (`_L` local, `_R` laptop) and pooled.
     This asserts they really are one cell before anything pools them.

⛔⛔ **IS-D1 IS BINDING ON EVERY ADDRESS.** Config-shaped values resolve from
`manifest.json`; statistics from `summary.json`, **which carries no config block
at all**. A precheck that reads `config` off `summary.json` gets `{}` — it fails
closed on one conjunct and passes **vacuously** on another. `resolve()` therefore
returns the ADDRESS that answered, and every gate prints it.

⛔ **ABSENT IS FAIL, never a skip and never a default** (`READ_RULE.md` §4).
"""
from __future__ import annotations

import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# =========================================================================== #
# 0. FROZEN CONSTANTS — the pair is law; these restate it, they do not decide  #
# =========================================================================== #

#: `DESIGN.md` §5 / `READ_RULE.md` header. ⛔ PROPOSED, NOT CLAIMED at build time.
BAND = 154_000_000_000
#: The throwaway sub-range the `IDENT` cell and the §9 smoke play. ⛔ NEVER in
#: the band claim — it buys no decks of the round.
THROWAWAY_BASE = 154_999_999_000

#: `READ_RULE.md` §3 — THE PHASE WINDOWS, FROZEN. ⚠️ `k=48` and `k=24` match NO
#: interval (both cut ends are strict) and fall through to `"late"`. Reproduced,
#: NOT repaired: a build that "fixes" the edge VOIDS the round, because it would
#: no longer be measuring the axis the census, the CL-070 root bank and
#: `split_tiearb2.py`'s strata are keyed on.
PHASE_CUTS = {"early": (48, 10**9), "mid": (24, 48), "late": (-1, 24)}
#: The seven values `DESIGN.md` §2.2 obtained by EXECUTING the canonical
#: `sample_agreement_roots.phase_bucket`, pinned here so the instrument carries
#: its own copy of the golden table.
PHASE_GOLDEN = ((71, "early"), (49, "early"), (48, "late"), (47, "mid"),
                (25, "mid"), (24, "late"), (23, "late"))

#: `DESIGN.md` §2.4 — the frozen arbiter rung. ⚠️ NOT the production rung:
#: `PRODUCTION.yaml` has carried `B=64` since 2026-08-20. The price of that
#: divergence rides on every branch (`DESIGN.md` §2.3).
ARB_B, ARB_J = 16, 4
ARB_MODE = "argmax"
ARB_SALT = "tiearb2-deploy-v1"
ARB_EPS = 0.0

#: `DESIGN.md` §2.4 — identical on BOTH sides.
LEAF_HASH = "a36d2e15a3b3d71d"
LEAF_CURVE = "curve125"
K_DETS, SIMS_PER_DET, TOTAL_SIMS = 8, 1376, 11008
EXACT_K, EXACT_MODE = 2, "marginalized"
RULES_PROFILE = "fixed_v1"
BACKEND = "rust"

#: `READ_RULE.md` §4 `G-SAT` — a RAIL check, not a strength bar.
SAT_BAND = (0.35, 0.65)
#: `READ_RULE.md` §4 `G-FAILSOFT` — REPORT-ONLY above the floor.
FAILSOFT_MAX_RATE = 0.01
#: `READ_RULE.md` §4 `G-N`.
N_COMMON_FLOOR_FRACTION = 0.80
FAILURE_RATE_VOID = 0.02

#: `READ_RULE.md` §4.0 `G-ANCHOR` and §5's ladder.
ANCHOR_Z = 2.0
BAR = 0.80                 #: `DESIGN.md` §4.1 — a DECISION bar, not a significance one.
PROPORTIONAL_COMPANION = 1.038   #: 0.3380 x 3.07. ⛔ NEVER a branch input.
BRANCH_Z = 2.0

#: `DESIGN.md` §3.1 — the sizing constant, derived from Stage-2 Phase B cell
#: `ARB` and nothing else (`M +3.0700`, `paired_z +4.445`, `n_paired 400 DECKS`).
#: ⛔ POWER ARITHMETIC ONLY. `READ_RULE.md` §1: never a denominator in a branch
#: test — every branch is adjudicated at the cell's OWN REALIZED SE.
SIGMA_D_MODEL = 13.81
#: Realized cross-cell correlation between two arbiter cells on one deck set
#: (`b64_cell/verdicts/READOUT_B64.md`). ⛔ Deck-matching buys a 6.4% SE
#: reduction and NOTHING MORE — never size on an assumed CRN gain.
RHO_CROSS_CELL = 0.1237
#: Flag (never void) a realized/modelled SE ratio outside this band.
SE_ANOMALY_BAND = (0.70, 1.43)

#: `RECON` tolerance (`READ_RULE.md` §1.1).
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

#: Prior-band context. ⛔⛔ DESCRIPTIVE OVERLAYS ONLY (`READ_RULE.md` §1.2):
#: never pooled, never z-combined, never a gate input. In particular `G-ANCHOR`
#: tests `z_full >= +2.0` AGAINST ZERO — ⛔ never an equality test against +3.07,
#: which is exactly the cross-band comparison CL-068 forbids.
PRIOR_BANDS = {
    "tiearb2_stage2 Phase B cell ARB": {"band": 132_000_000_000, "M": 3.0700,
                                        "z": 4.445, "n_decks": 400},
    "tiearb_widening b64_cell arm NARROW": {"band": 139_000_000_000, "M": 3.6607,
                                            "n_decks": 750},
}


# =========================================================================== #
# 1. THE CELLS                                                                 #
# =========================================================================== #

@dataclass(frozen=True)
class CellSpec:
    """One archive. ⚠️ `ARB_EARLY` is TWO archives (`_L` + `_R`) that are ONE
    cell — see `pool_key`."""
    name: str
    role: str                 #: "local" | "laptop" — `G-HOST`'s frozen box
    phase_gate: str           #: `G-GATE`'s frozen expectation, EXACTLY
    arb_enabled: bool
    seed_start: int
    n_decks: int
    pool_key: str             #: cells sharing this are pooled for the primary
    purpose: str

    @property
    def n_games(self) -> int:
        return self.n_decks * 2

    @property
    def seed_end(self) -> int:
        """INCLUSIVE last seed of this cell's own range."""
        return self.seed_start + self.n_decks - 1


#: ⭐ OPTION A1 (`SIZING_ETA.md` §1, the recommendation), in the BALANCED shape
#: `DESIGN.md` §6.5 prefers: `ARB_EARLY` split into two same-config sub-cells on
#: DISJOINT deck sub-ranges of ONE band, pooled for the primary. That pooling is
#: within-band and same-config, which is the one legitimate kind (CL-068).
CELLS: tuple[CellSpec, ...] = (
    CellSpec("IDENT", "local", "none", True, THROWAWAY_BASE, 40, "IDENT",
             "⭐ PREFLIGHT — gate-off must BE the champion. Proves the knob "
             "reached the HARNESS (the G-J4 / inverted-liveness class). "
             "Adjudicated |z| <= 2.0, never a strength read."),
    CellSpec("ARB_FULL", "laptop", "all", True, BAND, 400, "ARB_FULL",
             "⭐ THE ANCHOR — does the arbiter still win in this band, on this "
             "build, at B=16? G-ANCHOR is a HARD ORDERING: if it does not "
             "convict, NO branch on any gated cell is taken."),
    CellSpec("ARB_EARLY_L", "local", "early", True, BAND, 1037, "ARB_EARLY",
             "⭐⭐ THE PRIMARY (local sub-cell) — do EARLY fires carry "
             "game-level value, judge-free?"),
    CellSpec("ARB_EARLY_R", "laptop", "early", True, BAND + 1037, 163, "ARB_EARLY",
             "⭐⭐ THE PRIMARY (laptop sub-cell) — same config, disjoint deck "
             "sub-range, pooled with _L."),
)
#: ⚠️ `ARB_FULL`'s 400 decks are the FIRST 400 of `ARB_EARLY`'s 1,200 — the
#: `n_common` of the `FULL − EARLY` deck-paired COMPANION (`DESIGN.md` §4.4).
#: ⛔ That contrast is NEVER a branch input.
POOLS = ("IDENT", "ARB_FULL", "ARB_EARLY")


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"unknown cell {name!r}; known: {[c.name for c in CELLS]}")


def cells_of_pool(pool: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.pool_key == pool)


def cells_of_box(role: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.role == role)


# =========================================================================== #
# 2. THE PHASE WINDOW — the instrument's own copy of the canonical function    #
# =========================================================================== #

def phase_bucket(k_remaining: int) -> str:
    """`sample_agreement_roots.phase_bucket`, reproduced. ⚠️ STRICT on BOTH ends
    with a `"late"` fall-through, so `k=48` and `k=24` are `"late"`."""
    for name, (lo, hi) in PHASE_CUTS.items():
        if lo < k_remaining < hi:
            return name
    return "late"


def phase_windows() -> dict:
    """`{"early": [49, 71], "mid": [25, 47], "late": [0, 23] + [24, 48]}` —
    resolved to the integers `READ_RULE.md` §3 freezes, computed rather than
    typed so the table cannot drift from the function."""
    out: dict[str, list[int]] = {"early": [], "mid": [], "late": []}
    for k in range(0, 72):
        out[phase_bucket(k)].append(k)
    return out


# =========================================================================== #
# 3. ADDRESS RESOLUTION — IS-D1                                                #
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

    An address is `"<document>:<dotted.path>"`, e.g.
    `"manifest:config.cand_tiearb.phase_gate"`. ⛔ EVERY gate prints the address
    that answered: IS-D1's defect was a precheck that read `config` off
    `summary.json` — which carries NO config block at all — got `{}`, failed
    closed on one conjunct and passed VACUOUSLY on another.
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
# 4. REV / PROVENANCE — carried from invasion r3 (the IS-A1 fold)              #
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
                        "prevent exactly it. ⚠️ NOTE THIS IS THE PINS "
                        "DISAGREEING, NOT THE SHORT REVS — the short revs "
                        "disagreeing is EXPECTED and harmless (IS-A1).")}
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
# 5. THE STATISTIC — `RECON`'s independent re-implementation                   #
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


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from the raw records.

    ⚠️ `READ_RULE.md` §4.4/§5.1: **`elo` may never be quoted bare.** Stage 2's
    own secondary did not convict (`+23.92`, CI `[−0.21, +48.06]`, winrate
    z `+1.94`) and a phase SLICE of it is weaker still. The margin is the
    statistic; the winrate is not."""
    scored = [r for r in records if isinstance(r, Mapping) and "diff" in r]
    n = len(scored)
    if n == 0:
        return {"n": 0, "W": 0, "D": 0, "L": 0, "winrate": None, "elo": None,
                "elo_sig_1sigma": None, "avg_diff": None}
    w = sum(1 for r in scored if r.get("won_by_champ") is True)
    d = sum(1 for r in scored if r.get("drew") is True)
    wr = (w + 0.5 * d) / n
    if 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1.0 - wr))
        sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, sig = math.copysign(800.0, wr - 0.5), float("nan")
    return {"n": n, "W": w, "D": d, "L": n - w - d, "winrate": wr, "elo": elo,
            "elo_sig_1sigma": sig,
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
    """`SIGMA_D_MODEL / sqrt(n)`. 1,200 decks -> 0.3987. ⛔ POWER ARITHMETIC
    ONLY — never a denominator in a branch test."""
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


def se_cross_cell(n_common: int) -> float:
    """`se(FULL − EARLY) = sqrt(2) * (SIGMA_D/sqrt(n)) * sqrt(1 - rho)`.
    ⛔ `sqrt(1 - 0.1237) = 0.936` — deck-matching buys a **6.4% SE reduction**
    and nothing more. Never size a design on an assumed CRN gain."""
    return (math.sqrt(2.0) * (SIGMA_D_MODEL / math.sqrt(float(n_common)))
            * math.sqrt(1.0 - RHO_CROSS_CELL))


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def power_at(delta: float, se: float, bar: float = BAR) -> float:
    """P(the cell fires `E-LIVE`) at a true effect `delta`. ⚠️ At n=1,200 a TRUE
    +0.80 gives z = 2.01 — **50% power**. What the `n` guarantees is the
    BOUNDING direction (`E-DEAD` returns a real 95% bound), which is the branch
    the decision turns on (`DESIGN.md` §4)."""
    if se is None or se <= 0:
        return float("nan")
    # E-LIVE needs BOTH M >= bar and z >= BRANCH_Z; the binding one is the larger
    thresh = max(bar, BRANCH_Z * se)
    return 1.0 - _phi((thresh - delta) / se)


# =========================================================================== #
# 6. THE BRANCH LADDER — `READ_RULE.md` §5, pre-registered and EXHAUSTIVE      #
# =========================================================================== #

BRANCHES = ("U-VOID-INSTRUMENT", "U-VOID-ANCHOR", "E-REVERSED", "E-LIVE",
            "E-DEAD", "E-UNRESOLVED")


def branch_for_cell(M, se, z, *, gates_ok: bool, anchor_ok: bool,
                    suffix: str = "") -> str:
    """The §5 ladder, IN ORDER. First match wins.

    ⛔ Exclusive and exhaustive BY CONSTRUCTION, and ORDERED rather than
    disjoint: branch 2 (`E-REVERSED`) requires `M <= 0 ∧ z <= -2`, which forces
    `UB95 = M + 2SE <= 0 < +0.80`, so it would ALSO satisfy branch 4
    (`E-DEAD`) — which is exactly why it is checked first.
    """
    if not gates_ok:
        return "U-VOID-INSTRUMENT"
    if not anchor_ok:
        return "U-VOID-ANCHOR"
    if M is None or se is None or z is None:
        return "U-VOID-INSTRUMENT"
    ub95 = M + 2.0 * se
    if M <= 0.0 and z <= -BRANCH_Z:
        return "E-REVERSED" + suffix
    if M >= BAR and z >= BRANCH_Z:
        return "E-LIVE" + suffix
    if ub95 < BAR:
        return "E-DEAD" + suffix
    return "E-UNRESOLVED" + suffix


def branch_grid(step: float = 0.05, se_values=(0.2, 0.3, 0.399, 0.5, 0.8)) -> dict:
    """⭐ `READ_RULE.md` §5's own demand: sweep a dense `(M, SE)` grid and prove
    EXACTLY ONE branch fires at every point. Returns a histogram plus any point
    that matched none or more than one (which cannot happen — the ladder returns
    a single string — so the real content is that every branch is REACHABLE,
    §4.1's "no branch is unreachable by construction")."""
    seen: dict[str, int] = {}
    m = -6.0
    pts = 0
    while m <= 6.0 + 1e-9:
        for se in se_values:
            z = m / se
            b = branch_for_cell(m, se, z, gates_ok=True, anchor_ok=True)
            seen[b] = seen.get(b, 0) + 1
            pts += 1
        m += step
    return {"points": pts, "histogram": seen,
            "reachable": sorted(seen),
            "all_reachable": set(seen) >= {"E-REVERSED", "E-LIVE", "E-DEAD",
                                           "E-UNRESOLVED"}}


RIDERS_E_LIVE = (
    "⛔⛔ E-LIVE DOES NOT PROVE FAMILY-BLINDNESS. The in-family oracle's early "
    "cut read +0.1148 with F = 1.303 — a POSITIVE point estimate with F ABOVE "
    "1.0. The honest statement is 'the oracle could not RESOLVE early capture at "
    "n=300', NEVER 'the oracle read zero'. E-LIVE is fully consistent with the "
    "offline cut simply having been UNDERPOWERED, which would teach nothing "
    "about family-blindness. Corroboration must be judge-free or out-of-family "
    "(F4: a +1.49 in-family ceiling read -0.64 at z -3.8 out-of-family on the "
    "same CRN worlds) and is NOT funded here.",
    "⛔ It does not measure the owner-hole. No branch touches measurement/e4_games/.",
    "⛔ It does not license a phase-gated deploy. The cells are a decomposition "
    "instrument; ARB_EARLY's ~27% lower cost is a SCHEDULING FACT, never a finding.",
    "⛔ It is a B=16 result. PRODUCTION.yaml runs B=64. Transfer is an ASSUMPTION, "
    "and the offline Delta(16->64) may not be projected into game points.",
    "⛔ The slices need not sum to ARB_FULL and nothing tests that they do.",
    "⚠️ elo may never be quoted bare. The margin is the statistic.",
)
RIDERS_E_DEAD = (
    "⚠️ E-DEAD BOUNDS; IT DOES NOT ZERO. The reading is 'below +0.80 at 95%', "
    "never 'early fires are worthless'.",
    "⚠️ It is a bound AT B=16. A wider arbiter could plausibly clear the bar "
    "early; this round does not measure that and the offline increment may not "
    "be projected into game points.",
    "⭐ It DOES discharge the funded decision: on this evidence, terminal-"
    "grounded rollouts are not a cheap early-game steering ruler, and steering "
    "work should not be funded off them.",
)
RIDERS_ALWAYS = (
    "⛔ The slices do not sum to the whole and NO gate tests that they do "
    "(DESIGN §1.2): gating changes which move is played, so ARB_EARLY and "
    "ARB_FULL play DIFFERENT GAMES. A shortfall or an overshoot is EXPECTED "
    "behaviour of a decomposition by intervention, never an anomaly.",
    "⛔ Prior-band figures (+3.07 on 132e9, +3.66 on 139e9) are CONTEXT ONLY — "
    "never pooled, never z-combined, never a gate input (CL-068: 1.8-2.2x "
    "over-dispersion on cross-band contrasts, in BOTH statistics).",
    "⛔ governance/PRODUCTION.yaml is UNTOUCHED on every branch.",
)


# =========================================================================== #
# 7. THE ROUND-SPECIFIC GATES — the three DESIGN §7.6 names                     #
# =========================================================================== #

def decks_gate(spec: CellSpec, records: Sequence[Mapping],
               all_specs: Sequence[CellSpec] = CELLS) -> dict:
    """⛔ `G-DECKS` — **REWRITTEN, NOT COPIED** from invasion r3.

    ⭐ THIS ROUND'S RANGES **OVERLAP BY DESIGN** (`DESIGN.md` §5): `ARB_FULL`'s
    400 decks are a SUBSET of `ARB_EARLY`'s 1,200, because a DECOMPOSITION wants
    ONE deck set (it kills the deck-draw confound, lets one deck set be proven,
    and keeps every contrast WITHIN-BAND — the only robust class under CL-068).
    Invasion r3's disjointness clause would VOID EVERY HEALTHY CELL here.

    What IS asserted:
      (a) every realized seed lies inside **this cell's own** range;
      (b) no deck appears at one seat only (a half-played deck is DROPPED from
          the statistic and must SURFACE here, never be zero-filled);
      (c) `n_common` equals the cell's frozen `n_decks`;
      (d) ⭐ the SUB-CELLS of one pool are DISJOINT and EXHAUST the pool's range
          — the only disjointness this round asserts, and it is WITHIN a cell,
          not between cells.
    """
    by_deck = _by_deck(records)
    seeds = sorted(by_deck)
    lo, hi = spec.seed_start, spec.seed_end
    out_of_range = [s for s in seeds if not (lo <= s <= hi)]
    half = sorted(s for s, v in by_deck.items() if not (0 in v and 1 in v))
    n_common = len(per_deck_margins(records))
    sibs = [c for c in all_specs if c.pool_key == spec.pool_key]
    ranges = sorted((c.seed_start, c.seed_end, c.name) for c in sibs)
    overlaps = [(a[2], b[2]) for a, b in zip(ranges, ranges[1:]) if b[0] <= a[1]]
    contiguous = all(b[0] == a[1] + 1 for a, b in zip(ranges, ranges[1:]))
    ok = (not out_of_range and not half and n_common == spec.n_decks
          and not overlaps and contiguous)
    return gate(
        "G-DECKS", ok,
        {"range": [lo, hi], "n_seeds": len(seeds), "n_common": n_common,
         "frozen_n_decks": spec.n_decks, "out_of_range": out_of_range[:20],
         "half_played_decks": half[:20],
         "pool_subranges": [[a, b, n] for a, b, n in ranges],
         "subcell_overlaps": overlaps, "subcells_contiguous": contiguous},
        "raw seed*_a*.json",
        ("every realized seed is inside this cell's own range, both seatings are "
         "present on every deck, n_common == the frozen n, and the pool's "
         "sub-cells are disjoint and contiguous. ⚠️ CROSS-CELL RANGE OVERLAP IS "
         "BY DESIGN and is NOT tested here." if ok else
         "⛔ G-DECKS FAILED: " + "; ".join(filter(None, [
             f"{len(out_of_range)} seed(s) outside [{lo},{hi}]" if out_of_range else "",
             f"{len(half)} deck(s) played at ONE seat only" if half else "",
             (f"n_common {n_common} != frozen {spec.n_decks}"
              if n_common != spec.n_decks else ""),
             f"sub-cell ranges overlap: {overlaps}" if overlaps else "",
             "sub-cell ranges do not exhaust the pool range" if not contiguous else "",
         ]))))


def leaf_gate(cand_hash, opp_hash, cand_curve) -> dict:
    """⛔ `G-LEAF` — **REWRITTEN, NOT COPIED** from invasion r3, where the two
    sides' leaf hashes DIFFER by design.

    ⭐ HERE THEY MUST BE **EQUAL**, and equal to `a36d2e15a3b3d71d`. The arbiter
    is a post-search ROOT hook, not a leaf term: it moves NO leaf hash. A cell
    whose two leaf hashes differ is MISCONFIGURED and voids — and, note, a
    moved-hash check can never prove this surface LIVE, which is why `G-GATE`
    and `G-PHI` exist."""
    same = (cand_hash is not None and cand_hash == opp_hash)
    right = cand_hash == LEAF_HASH
    # PG-A1: compare the RESOLVED curve125 values, not the label string — the
    # original `str(cand_curve) == "curve125"` was unsatisfiable by construction
    # (see AMENDMENTS.md PG-A1, defect 1; ground truth = PRODUCTION.yaml C5 fold).
    curve125_values = [-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25]
    curve_ok = list(cand_curve or []) == curve125_values
    ok = same and right and curve_ok
    return gate("G-LEAF", ok,
                {"cand_leaf_hash": cand_hash, "opp_leaf_hash": opp_hash,
                 "expected": LEAF_HASH, "cand_curve": cand_curve},
                "manifest:config.{cand,opp}_leaf_hash",
                ("both sides carry the SAME leaf a36d2e15a3b3d71d (curve125) — "
                 "the arbiter is a root hook, not a leaf change" if ok else
                 "⛔ G-LEAF FAILED: " + "; ".join(filter(None, [
                     "the two sides' leaf hashes DIFFER (misconfigured cell — "
                     "the arbiter moves no leaf hash)" if not same else "",
                     f"leaf hash is not {LEAF_HASH}" if not right else "",
                     f"v29_meeple_curve is not {LEAF_CURVE}" if not curve_ok else "",
                 ]))))


#: Every config-shaped key `G-SUBPOOL` requires to be BYTE-IDENTICAL across the
#: sub-cells of one pool. ⚠️ `host` and the deck range are DELIBERATELY absent:
#: they are the two things that are SUPPOSED to differ.
SUBPOOL_ALIASES = (
    "config.cand_tiearb.enabled", "config.cand_tiearb.B", "config.cand_tiearb.J",
    "config.cand_tiearb.mode", "config.cand_tiearb.salt", "config.cand_tiearb.eps",
    "config.cand_tiearb.phase_gate",
    "config.cand_leaf_hash", "config.opp_leaf_hash",
    "config.champion.k_dets", "config.champion.sims_per_det",
    "config.champion.total_sims",
    "config.endgame.exact_k", "config.endgame.mode",
    "config.backend.name", "rules_profile.name",
    "carc_rs_build",
)


def subpool_gate(manifests_by_cell: Mapping[str, Mapping],
                 pool: str = "ARB_EARLY") -> dict:
    """⭐ `G-SUBPOOL` — NEW in this round (`DESIGN.md` §6.5).

    `ARB_EARLY_L` and `ARB_EARLY_R` are ONE CELL IN TWO ARCHIVES: identical
    config, DISJOINT deck sub-ranges of ONE band, pooled for the primary. That
    pooling is within-band and same-config, which is legitimate in a way
    cross-band pooling never is (CL-068) — but only if they really are the same
    cell. This asserts it BEFORE anything pools them.

    ⛔ Two sub-cells that differ on any frozen alias are NOT one cell and the
    pooled primary would be a mixture, not a measurement."""
    subs = [c.name for c in cells_of_pool(pool)]
    present = [n for n in subs if n in manifests_by_cell]
    docs = {n: {"manifest": manifests_by_cell[n]} for n in present}
    disagree, resolved = {}, {}
    for alias in SUBPOOL_ALIASES:
        vals = {}
        for n in present:
            v, addr = resolve(docs[n], f"manifest:{alias}")
            vals[n] = ("ABSENT" if v is MISSING else v)
        resolved[alias] = vals
        if len(set(map(repr, vals.values()))) > 1 or "ABSENT" in vals.values():
            disagree[alias] = vals
    ok = bool(present) and len(present) == len(subs) and not disagree
    return gate("G-SUBPOOL", ok,
                {"pool": pool, "sub_cells": subs, "present": present,
                 "disagreements": disagree, "resolved": resolved},
                "both sub-cell manifests",
                (f"{present} carry byte-identical config across every frozen "
                 "alias — they are ONE cell in two archives" if ok else
                 "⛔ G-SUBPOOL FAILED: " + ("missing sub-cell archive(s) "
                                            f"{sorted(set(subs) - set(present))}"
                                            if len(present) != len(subs) else
                                            f"config disagrees at {sorted(disagree)} "
                                            "(or is ABSENT, which is FAIL)")))


def phi_gate(spec: CellSpec, fired: Mapping) -> dict:
    """⭐⭐ `G-PHI` — the window bit, PROVEN FROM PLAY.

    `G-GATE` proves the knob was SET (config); this proves it BOUND. It is the
    second independent witness and the only one derived from play — which is why
    `ABSENT` is `FAIL` here too: a wheel predating the counters emits nothing,
    and "no key" must never read as "that phase had no fires".

    `fired` is `{"early": n, "mid": n, "late": n, "total": n}`.
    """
    need = ("early", "mid", "late", "total")
    absent = [k for k in need if fired.get(k) is None]
    if absent:
        return gate("G-PHI", False, {"fired": dict(fired), "absent": absent}, None,
                    f"⛔ per-phase fire counters ABSENT ({absent}) — ABSENT is "
                    "FAIL. A stale wheel serves an UNGATED arbiter, which on "
                    "ARB_EARLY *is* ARB_FULL.")
    e, m, la, tot = (int(fired[k]) for k in need)
    g = spec.phase_gate
    if g == "none":
        ok = (e, m, la, tot) == (0, 0, 0, 0)
        why = ("all four counters are 0 — the armed knob fired nowhere" if ok else
               "⛔ a gate=none cell FIRED; it is not the champion")
    elif g == "all":
        ok = e > 0 and m > 0 and la > 0 and e + m + la == tot
        why = ("all three phases fired and they PARTITION fired_plies" if ok else
               "⛔ an ungated cell must fire in all three phases and the three "
               f"must sum to fired_plies ({e}+{m}+{la} vs {tot})")
    else:
        idx = {"early": e, "mid": m, "late": la}
        ok = idx[g] > 0 and all(v == 0 for k, v in idx.items() if k != g)
        why = (f"fired ONLY in {g} ({idx[g]} plies) — the window BOUND" if ok else
               f"⛔ a gate={g} cell fired outside its window: {idx}")
    return gate("G-PHI", ok,
                {"phase_gate": g, "fired_early": e, "fired_mid": m,
                 "fired_late": la, "fired_plies": tot,
                 "shares": ({k: v / tot for k, v in
                             (("early", e), ("mid", m), ("late", la))}
                            if tot else None),
                 "design_6_2_proxy_shares": {"early": 0.3380, "mid": 0.3059,
                                             "late": 0.3561},
                 "proxy_note": ("DESIGN §6.2's shares are RAW exact-tie shares "
                                "from a DIFFERENT rules epoch with no repr-dedup "
                                "column on disk. The shares above are the "
                                "DEDUPED runtime split and SUPERSEDE the proxy "
                                "for sizing. Meaningful only on a gate=all cell.")},
                "summary:tiearb_fired_*_total (statistics) / "
                "manifest:cand_tiearb.fired_* (realized, patched at close-out)",
                why)


# =========================================================================== #
# 8. SELF-CHECK — the library's own invariants                                 #
# =========================================================================== #

def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean.
    ⛔ Run by `analyze_phasegate.py --selftest`; a non-empty list is a build
    failure, not a round failure."""
    p: list[str] = []
    # the golden table, against this file's own reproduction of the function
    for k, want in PHASE_GOLDEN:
        if phase_bucket(k) != want:
            p.append(f"phase_bucket({k}) = {phase_bucket(k)!r}, want {want!r}")
    w = phase_windows()
    if w["early"] != list(range(49, 72)):
        p.append(f"early window is {w['early'][:3]}..., want [49..71]")
    if w["mid"] != list(range(25, 48)):
        p.append(f"mid window is {w['mid'][:3]}..., want [25..47]")
    if w["late"] != sorted(list(range(0, 24)) + [24, 48]):
        p.append("late window is not [0..23] + {24, 48} — the fall-through moved")
    # the cells
    if {c.pool_key for c in CELLS} != set(POOLS):
        p.append("CELLS' pool keys do not match POOLS")
    early = cells_of_pool("ARB_EARLY")
    if sum(c.n_decks for c in early) != 1200:
        p.append(f"ARB_EARLY sub-cells sum to {sum(c.n_decks for c in early)}, want 1200")
    rng = sorted((c.seed_start, c.seed_end) for c in early)
    for a, b in zip(rng, rng[1:]):
        if b[0] != a[1] + 1:
            p.append(f"ARB_EARLY sub-ranges are not contiguous: {a} then {b}")
    full = cell_by_name("ARB_FULL")
    if not (full.seed_start == BAND and full.seed_end <= rng[-1][1]):
        p.append("ARB_FULL's range is not the first 400 of ARB_EARLY's — the "
                 "FULL-EARLY companion would not be deck-paired")
    if cell_by_name("IDENT").seed_start < THROWAWAY_BASE:
        p.append("IDENT is not on the throwaway sub-range")
    # the sizing arithmetic DESIGN §4 states
    if abs(se_model(400) - 0.6907) > 5e-4:
        p.append(f"se_model(400) = {se_model(400):.4f}, DESIGN §3.1 says 0.6907")
    if abs(se_model(1200) - 0.399) > 1e-3:
        p.append(f"se_model(1200) = {se_model(1200):.4f}, DESIGN §4 says 0.399")
    n_min = (2 * SIGMA_D_MODEL / BAR) ** 2
    if not (1190 <= n_min <= 1196):
        p.append(f"the §4(a) minimum n is {n_min:.0f}, DESIGN says 1193")
    if abs(se_cross_cell(1) - 18.28) > 0.01:
        p.append(f"se_cross_cell coefficient is {se_cross_cell(1):.2f}, want 18.28")
    # power, stated honestly
    pw = power_at(BAR, se_model(1200))
    if not (0.48 <= pw <= 0.52):
        p.append(f"power at a TRUE +0.80 and n=1200 is {pw:.3f}; DESIGN §4 says ~50%")
    # the ladder
    g = branch_grid()
    if not g["all_reachable"]:
        p.append(f"not every §5 branch is reachable: {g['reachable']}")
    if branch_for_cell(0.0, 0.4, 0.0, gates_ok=False, anchor_ok=True) != "U-VOID-INSTRUMENT":
        p.append("a failed gate does not void first")
    if branch_for_cell(5.0, 0.4, 12.5, gates_ok=True, anchor_ok=False) != "U-VOID-ANCHOR":
        p.append("a failed anchor does not void a firing gated cell")
    # ordering: E-REVERSED must win over E-DEAD even though both would match
    if branch_for_cell(-2.0, 0.4, -5.0, gates_ok=True, anchor_ok=True) != "E-REVERSED":
        p.append("E-REVERSED is not checked before E-DEAD")
    if branch_for_cell(0.0, 0.3, 0.0, gates_ok=True, anchor_ok=True) != "E-DEAD":
        p.append("a tight null does not read E-DEAD")
    if branch_for_cell(0.0, 0.8, 0.0, gates_ok=True, anchor_ok=True) != "E-UNRESOLVED":
        p.append("a WIDE null does not read E-UNRESOLVED — it must not read DEAD")
    if branch_for_cell(1.2, 0.4, 3.0, gates_ok=True, anchor_ok=True) != "E-LIVE":
        p.append("a clear positive does not read E-LIVE")
    # the proportional companion
    if abs(0.3380 * 3.07 - PROPORTIONAL_COMPANION) > 5e-4:
        p.append("PROPORTIONAL_COMPANION is not 0.3380 x 3.07")
    return p


if __name__ == "__main__":                                    # pragma: no cover
    probs = sanity_check()
    print(json.dumps({"sanity_problems": probs,
                      "phase_windows": {k: [v[0], v[-1]] if v else []
                                        for k, v in phase_windows().items()},
                      "cells": [c.name for c in CELLS],
                      "branch_grid": branch_grid()}, indent=2))
    raise SystemExit(1 if probs else 0)
