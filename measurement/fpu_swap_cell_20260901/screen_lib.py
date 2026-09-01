#!/usr/bin/env python3
"""`screen_lib` — the FPU-SWAP CELL's shared instrument library.

⭐ A FORK of `measurement/fpu_resurrection_prep/screen_lib.py` (itself a fork of
`measurement/phasegate_prep/screen_lib.py`), carrying the hardened generic parts
verbatim in CONSTRUCTION (`resolve`/`gate`, `paired_margin`, `winrate_elo`,
`recon_close`, `rev_matches`/`is_hex40`, `host_matches_box`, `se_model`) and
REWRITING everything that is round-specific. This round is a SINGLE CELL, so the
multi-cell machinery (three bands, `CELLS` tuples, per-cell dispatch,
`decks_gate`'s cross-cell clash check) is DELETED, not carried — nothing here is
pooled with anything else, ever.

⛔⛔ **THE CELL IS ASYMMETRIC BY DESIGN — THIS IS NOT `G-ARB-OFF`.**
`fpu_resurrection_prep`'s `arb_off_gate` demanded the arbiter be OFF on BOTH
sides. THIS round demands the OPPOSITE shape on EACH side:

  * candidate = production champion + `fpu_reduction=0.2`, tie-arbiter **ABSENT**
    (no `--cand-tiearb-*` flag is ever passed — the harness's own convention for
    "this seat did not arbitrate", per `tiearb_gates.py`);
  * opponent  = the UNMODIFIED deployed champion, tie-arbiter **ARMED** at the
    full deployed spec (`--opp-tiearb-*`, B=64/J=4/argmax/tiearb2-deploy-v1/
    eps=0.0/phase_gate=all).

`tiearb_gates.assert_tiearb_sides` (2026-08-31, `scripts/classical_search/
tiearb_gates.py`) is imported rather than re-derived: it already encodes the two
sides' different absence conventions and is the module named in this round's own
funding brief as "the gate helper".

⛔ **ABSENT IS FAIL, never a skip and never a default** (the standing convention
of every prereg pair in this tree since `phasegate_prep`).

⚠️ **AMENDED PRE-LAUNCH, zero games run; amended blind commit = the commit
introducing this line.** Orchestrator review (statistics-blind — no cell
outcomes exist) found the original margin-only design under-weighted the axis
the funding brief's own arithmetic actually rests on: the declined-by-
arithmetic case is built on an ELO-DOMAIN gap (fpu-alone +26 elo vs arb-alone
+66/+69 elo, ≈+40 elo), not a margin-domain one — margin is where the two
surfaces are closest and most overlap-discounted, which is why the original
§4.3 table read 57-90% SWAP-UNRESOLVED. This amendment adds a CO-PRIMARY elo
leg (deck-paired elo advantage of the arb side, realized SE, decision-anchored
bar `BAR_ELO_LEG=15.0` ≈ 7× the arbiter's own clock-refund upside), Holm-
corrected against the margin leg (`HOLM_Z≈2.278` replaces `BRANCH_Z=2.0` as the
per-leg threshold both legs must individually clear), rewrites
`branch_for_cell` to a two-leg "fires if EITHER leg clears" ladder, and
recomputes the expected-read table — under the funding brief's own elo prior
(~+40), SWAP-KILLED becomes the modal branch (≈73-79%), reversing the original
table's headline. Nothing is retracted: the margin-only figures are correct as
far as they went; they were simply the wrong PRIMARY axis for this decision.
Full detail: `PREREG.md` §4 (amended).
"""
from __future__ import annotations

import math
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "scripts" / "classical_search"))

import tiearb_gates as TA  # noqa: E402

# =========================================================================== #
# 0. FROZEN CONSTANTS — the pair is law; these restate it, they do not decide  #
# =========================================================================== #

#: ⛔ PROPOSED, NOT CLAIMED at build time. See `BAND_CLAIMED.placeholder`: this
#: is a FRESH-DECK cell (unlike `e1b_armed_continuation_20260901`, which spent
#: no band) and the orchestrator claims exactly ONE band, after a tree sweep,
#: before launch. `170_000_000_000` is the proposed next-monotone-free id after
#: `fpu_h2h_r2_prep`'s `169_000_000_000` (governance/BAND_REGISTRY.csv, checked
#: 2026-09-01) — NOT a claim; the tree sweep at claim time is the binding check
#: (the `146e9` trap: a band absent from the registry but referenced in the
#: tree is NOT free).
PROPOSED_BAND = 170_000_000_000
#: Throwaway sub-range for the smoke + positive-control legs. Placed ~1e6 above
#: the proposed band's own span so it can never collide with the 400 real decks
#: even if the claimed band ends up shifted at launch time.
THROWAWAY_BASE = PROPOSED_BAND + 999_000
THROWAWAY_SPAN = 1_000

#: `DESIGN` — identical on BOTH sides. Carried from `fpu_resurrection_prep` /
#: `fpu_h2h_r2_prep`, both current at freeze time.
LEAF_HASH = "a36d2e15a3b3d71d"
#: ⭐ THE 2026-08-30 promoted desktop champion. BOTH sides run it — the budget is
#: NOT the variable under test.
K_DETS, SIMS_PER_DET, TOTAL_SIMS = 16, 1376, 22016
EXACT_K, EXACT_MODE = 2, "marginalized"
RULES_PROFILE = "fixed_v1"
BACKEND = "rust"

#: The single variable's frozen value.
FPU_DOSE = 0.2

#: The deployed tie-arbiter spec, cited from `tiearb_gates.py` rather than
#: retyped — a prereg that re-typed the seven keys could drift from the module
#: the adjudicator actually gates against.
DEPLOYED_TIEARB = dict(TA.DEPLOYED_TIEARB_B64)

#: `G-SAT` — a RAIL check, not a strength bar. Wider than the symmetric-cell
#: rounds' (0.35, 0.65): this cell's TWO simultaneous asymmetries (a knob AND an
#: arbiter moving in OPPOSITE directions across the seats) make a wider healthy
#: range than a single-variable cell, and `G-SAT`'s job is only to catch a
#: broken run, not to grade a good one.
SAT_BAND = (0.30, 0.70)
N_COMMON_FLOOR_FRACTION = 0.80
FAILURE_RATE_VOID = 0.02

#: ⭐ THE SIZING CONSTANT — carried UNCHANGED from `fpu_resurrection_prep` /
#: `fpu_h2h_r2_prep` (both cite the Stage-2 Phase B `ARB` cell,
#: `M +3.0700 pts/deck`, `paired_z +4.445`, `n_paired 400 decks`). ⛔ POWER
#: ARITHMETIC ONLY — never a denominator in any branch test; every branch is
#: adjudicated at the CELL'S OWN REALIZED SE.
SIGMA_D_MODEL = 13.81
SE_ANOMALY_BAND = (0.70, 1.43)
#: The realized SE this round is SIZED against: `se_model(400)`.
SE_400 = SIGMA_D_MODEL / math.sqrt(400.0)  # ≈ 0.6905

#: ⭐⭐ THE BAR — owner ruling 2026-08-30 ("effect size sounds right"), NEVER
#: 2·σ̂ of the instrument. `+1.0 pts/deck` is "the FPU chain's own bar class":
#: the SAME `LB95 >= +1.0` ADOPT bar the `fpu_h2h`/`fpu_h2h_r2` rounds used for
#: their (symmetric, both-seats-armed) cell — reused here for cross-round
#: comparability rather than re-derived, per DESIGN's own citation of it.
#: ⚠️ THIS IS NOT THE DECISION-RELEVANT BAR. The decision the funding brief
#: actually asks ("would the swap ever be reconsidered?") is set by the
#: ARBITER'S OWN CLOCK COST (~+2 elo ≈ ~0.35 pts/deck): the swap is attractive
#: only if fpu-alone is not worse than arb-alone by less than that. `0.35` is
#: UNRESOLVABLE at n=400 decks (`SE_400` alone is ~2x that), and `PREREG.md`
#: §4 says so explicitly rather than silently substituting the coarser bar for
#: the real question. `BAR_SWAP` is the AFFORDABLE read: the direction, at a
#: resolution this design can actually see.
BAR_SWAP = 1.0
BRANCH_Z = 2.0                      #: the `2·SE` convention this whole tree uses
                                     #: for `UB95`/`LB95` (not 1.645 — see PREREG §4.1)
                                     #: ⚠️ AMENDED PRE-LAUNCH: `BRANCH_Z` alone no
                                     #: longer decides a branch on either leg —
                                     #: `HOLM_Z` below does. `BRANCH_Z`/2σ values
                                     #: are still COMPUTED and REPORTED beside the
                                     #: Holm-adjusted ones, for comparison only.

#: `RECON` tolerance.
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

PAIRING_FACTOR = 1.0 / math.sqrt(2.0)          #: ≈ 0.70711

# =========================================================================== #
# 0.1 AMENDED PRE-LAUNCH — THE CO-PRIMARY ELO LEG (0 games run at amendment)   #
# =========================================================================== #
# ⚠️ AMENDED PRE-LAUNCH, zero games run; amended blind commit = the commit
# introducing this section. Orchestrator review found the margin-only design
# under-weighted the axis the funding brief's own arithmetic actually rests on:
# fpu-alone's +26 elo vs arb-alone's +66/+69 elo is an ELO-DOMAIN gap (~+40),
# not a margin-domain one — the margin domain is where the two surfaces are
# closest and most overlap-discounted (§4.3's own table showed 57-90%
# SWAP-UNRESOLVED under the margin-only ladder). This section adds elo as a
# CO-PRIMARY leg, Holm-corrected against the margin leg for the multiple
# comparison, per PREREG.md §4 (amended).


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _phi_inv(p: float, lo: float = -9.0, hi: float = 9.0) -> float:
    """Standard-normal quantile via bisection on `_phi` — no scipy dependency,
    and `_phi`/`_phi_inv` are then a matched, self-consistent pair rather than
    one exact (erf) and one approximated from a different source."""
    for _ in range(100):
        mid = (lo + hi) / 2.0
        if _phi(mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


#: ⭐⭐ THE HOLM-BONFERRONI CORRECTION, m=2 (margin leg, elo leg). For a
#: "reject if EITHER leg clears its bound" family test, Holm's step-down
#: procedure and plain Bonferroni agree exactly on the question that matters
#: here (does at least one hypothesis reject) — both compare the MOST extreme
#: leg's tail probability to `alpha/m`, so implementing this as "each leg
#: individually needs a HOLM_Z threshold instead of BRANCH_Z" is not an
#: approximation of Holm, it IS Holm for m=2 union rejection.
#: `HOLM_Z = Φ⁻¹(1 - (1-Φ(BRANCH_Z))/2) ≈ 2.2776` — HIGHER than `BRANCH_Z=2.0`
#: (a STRICTER per-leg bar), because testing two legs instead of one and still
#: wanting the same family-wise false-fire rate (~2.275% one-sided) means each
#: leg individually must clear a tighter bound.
HOLM_Z = _phi_inv(1.0 - (1.0 - _phi(BRANCH_Z)) / 2.0)          # ≈ 2.27760

#: ⭐⭐ THE ELO LEG'S BAR — decision-anchored, NOT `2·σ̂` of the instrument
#: (owner ruling 2026-08-30, carried into this amendment). Derivation: the
#: swap's ENTIRE upside is the arbiter's own clock refund, ≈ +2 elo redeployed
#: (PREREG §4.1's `~0.35 pts/deck` figure, in elo terms). `BAR_ELO_LEG = 15.0`
#: is ≈ 7× that refund — an arb-side elo edge bounded at or above this level
#: makes the swap dead on ANY plausible accounting of what the refund is worth,
#: not merely dead at this design's own resolution.
#: ⚠️ NOTE THE DISTINCTION EXPLICITLY (the orchestrator's own instruction):
#: at n=800 games (400 decks paired) the REALIZED elo se is typically close to
#: `SE_ELO_PLANNING ≈ 8.69` (see below), so `2·σ̂ ≈ 17.4` — i.e. **`BAR_ELO_LEG`
#: (15.0) is BELOW `2·σ̂` here**, the opposite relationship `BAR_SWAP` has to
#: its own `2·σ̂` (`BAR_SWAP=1.0 < 2·SE_400≈1.38` is also true, so both bars
#: happen to sit below their instrument's naive 2σ̂ — but `BAR_ELO_LEG` was
#: NOT set by halving or otherwise deriving it FROM `2·σ̂`; it was set from the
#: refund multiple above, and the fact that it lands below `2·σ̂` here is a
#: consequence of how good this leg's power is, not the derivation).
BAR_ELO_LEG = 15.0

#: The elo leg's SE at "the null footing" (`wr=0.5`) and n=800 games — the
#: PLANNING-TIME constant, exactly analogous to `SIGMA_D_MODEL`/`SE_400` for
#: the margin leg. ⚠️ `elo_sigma_paired` is DEFINED FURTHER DOWN in this file
#: (§3) — `SE_ELO_PLANNING` is computed there, after the definition, and
#: re-exported here in the constants block via a forward reference resolved at
#: import time (see the assignment beside `elo_sigma_paired`, sanity-checked
#: to match this comment's ≈8.686).
N_GAMES_REAL_CELL = 800

#: ⛔⛔ PRIOR ART. DESCRIPTIVE OVERLAYS ONLY — never pooled, never a gate input,
#: and every one of them is a DIFFERENT CELL SHAPE than this one (none of them
#: is fpu-alone vs arb-alone HEAD TO HEAD; this cell has never been played).
PRIOR_ART = {
    "fpu_resurrection_CELL_FPU02_F_RESURRECT_n800paired_b155e9 (2026-08-30)": {
        "shape": "candidate = champion + fpu 0.2, arb OFF both sides; "
                 "opponent = unmodified champion, arb OFF",
        "margin_pts_per_deck": 2.95125, "elo": 26.11, "elo_sigma": 8.71,
        "note": "CONFIRMED (LB95 +1.586 > BAR_M 1.381, z +4.32) — fpu-alone's "
                "advantage over PLAIN, with the arbiter absent on both sides.",
    },
    "fpu_h2h_deployed_config_H_UNRESOLVED_n800paired_b168e9 (2026-08-31)": {
        "shape": "candidate = champion + fpu 0.2, arb ON both sides (B64); "
                 "opponent = unmodified champion, arb ON both sides (B64)",
        "margin_pts_per_deck": 1.0188, "elo": 1.74, "elo_sigma": 8.69,
        "note": "UNRESOLVED (z +1.49 vs LB95>=+1.0 ADOPT bar) — fpu's MARGINAL "
                "value ON TOP OF an already-armed arbiter, both seats symmetric. "
                "⛔ NOT this cell's shape: here the arbiter is asymmetric.",
    },
    "fpu_h2h_r2_deployed_config_H_UNRESOLVED_n1600paired_b169e9 (2026-09-01)": {
        "shape": "same shape as round 1, n doubled to 1600 paired",
        "margin_pts_per_deck": 0.8612, "elo": None, "elo_sigma": None,
        "note": "UNRESOLVED (z +1.89, misses the +1.0 ADOPT bar by 0.05) — the "
                "effect held sign and shrank slightly with more n; consistent "
                "with 'the B64 arbiter absorbs most of the fpu repair surface'.",
    },
    "tiearb_widening_b32v64_gamecell_B64_minus_B32_n1497decks_b140e9 (2026-08-22),"
    " CELL_B64 vs the common UNMODIFIED opponent": {
        "shape": "candidate = champion + arb B64, arb ON; opponent = unmodified "
                 "champion, arb OFF (arb-alone vs plain, NOT this cell's fpu "
                 "axis at all)",
        "margin_pts_per_deck": 5.2123, "elo": 66.4644, "elo_sigma": 6.4597,
        "note": "the arb-alone advantage over PLAIN — the LEVER_INDEX '+66 elo "
                "internal' figure. ⛔ measured k8x1376=11008, NOT this round's "
                "k16x1376=22016 — a BUDGET-mismatched prior, disclosed.",
    },
    "carcasum_arbchallenge_D_on_minus_off_n200decks_b147e9 (2026-08-25),"
    " T-TRANSFER": {
        "shape": "external carcasum-engine cross-check of the same arb-alone-"
                 "vs-plain question",
        "elo": 69, "note": "'+69 elo external' vs '+66 elo internal' — an "
                "independent-engine corroboration of the arb-alone effect's "
                "SIGN and rough SIZE. z +4.4941.",
    },
    "docs/LEVER_INDEX.md 'FPU INSTEAD OF the tie-arbiter' row (2026-09-01,"
    " owner-provided arithmetic)": {
        "note": "the FUNDING BRIEF's own back-of-envelope: fpu-alone +26 elo "
                "vs arb-alone +66/+69 elo internal/external, 'expected net ≈ "
                "-40 elo' for the swap — i.e. an arb-side ELO advantage of "
                "~40 elo directly (AMENDED PRE-LAUNCH: this is now the "
                "co-primary elo leg's own prior, tested directly against "
                "BAR_ELO_LEG=15, rather than only glossed into margin terms). "
                "This cell is the DIRECT measurement the arithmetic stood in "
                "for.",
    },
}

#: ⭐ A first-order, NON-BINDING arithmetic reconstruction (companion only,
#: never a gate or branch input): if fpu's advantage over plain (+2.95 pts/deck,
#: arb off both sides) and arb's advantage over plain (+5.21 pts/deck, arb-alone
#: vs plain, budget-mismatched) were purely ADDITIVE deviations from "plain",
#: the naive prediction for THIS cell's M = candidate(fpu,arb-off) minus
#: opponent(arb-on) would be 2.95 - 5.21 ≈ -2.26 pts/deck, i.e. an arb-side
#: advantage of ≈ +2.26 pts/deck. The fpu_h2h rounds' own finding — fpu's
#: marginal value ON TOP OF an armed arbiter collapses from ~2.95 to ~0.86-1.02
#: — is direct evidence AGAINST pure additivity (the two surfaces overlap), so
#: this reconstruction is presented as an UPPER-BOUND-ish companion beside the
#: funding brief's own ~+1.5/deck figure, not as a better prior.
ARITHMETIC_RECONSTRUCTION_ARB_ADVANTAGE = 2.26
FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR = 1.5


# =========================================================================== #
# 1. ADDRESS RESOLUTION — IS-D1, carried verbatim in construction              #
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
    `MISSING` is not `None`: a resolved `null` is a POSITIVE statement."""
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
    """One gate's verdict record. `ABSENT` is `FAIL`, so an unresolved value
    arrives here as `ok=False` with `address=None` — never as a skip."""
    return {"gate": gid, "ok": bool(ok), "detail": detail,
            "address": addr or "ABSENT (no address answered) — ABSENT is FAIL",
            "why": why}


# =========================================================================== #
# 2. REV / PROVENANCE                                                         #
# =========================================================================== #

def split_dirty(code_rev: str) -> tuple[str, bool]:
    s = (code_rev or "").strip()
    if s.lower().endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def is_hex40(s) -> bool:
    return (isinstance(s, str) and len(s) == 40
            and all(c in "0123456789abcdef" for c in s.lower()))


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """`(ok, why)` — does a manifest's short `code_rev` NAME `PINNED_SRC_REV`?"""
    if not code_rev or not isinstance(code_rev, str):
        return False, "code_rev ABSENT — ABSENT is FAIL"
    if not pinned or not isinstance(pinned, str):
        return False, "PINNED_SRC_REV ABSENT — ABSENT is FAIL"
    cr, dirty = split_dirty(code_rev)
    cr, pn = cr.lower(), pinned.strip().lower()
    note = ("; ⚠️ whole-tree `-dirty` marker present — INFORMATIONAL ONLY"
            if dirty else "")
    if not is_hex40(pn):
        return False, f"PINNED_SRC_REV {pinned!r} is not a 40-hex sha{note}"
    if len(cr) < MIN_REV_PREFIX or any(c not in "0123456789abcdef" for c in cr):
        return False, f"code_rev {code_rev!r} is not >= {MIN_REV_PREFIX} hex chars{note}"
    if not pn.startswith(cr):
        return False, (f"code_rev {code_rev!r} is not a prefix of PINNED_SRC_REV "
                       f"{pinned!r}{note}")
    return True, f"code_rev {code_rev!r} names PINNED_SRC_REV {pinned!r}{note}"


_HOST_ALIASES = {"laptop": ("laptop", "laptop-wsl", "laptop-pop", "pop-os", "pop"),
                 "local": ("doctor", "5800x", "desktop", "local")}


def host_matches_box(observed_host, role: str) -> tuple[bool, str]:
    if not observed_host or not isinstance(observed_host, str):
        return False, "host ABSENT — ABSENT is FAIL"
    h = observed_host.strip().lower()
    for alias in _HOST_ALIASES.get(role, ()):
        if alias in h:
            return True, f"host {observed_host!r} matches box role {role!r} (via {alias!r})"
    if role == "local" and not any(a in h for a in _HOST_ALIASES["laptop"]):
        return True, f"host {observed_host!r} is not the laptop ⇒ treated as {role!r}"
    return False, f"host {observed_host!r} does not match box role {role!r}"


# =========================================================================== #
# 3. THE STATISTIC                                                            #
# =========================================================================== #

def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}`. A record missing `seed`, `a_seat` or `diff` is
    DROPPED — it surfaces at `G-DECKS` as a short `n_paired`, never zero-filled."""
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
    """`D(d) = (diff(d, a_seat=0) + diff(d, a_seat=1)) / 2` over decks appearing
    in BOTH seatings. `diff` is CANDIDATE minus OPPONENT in points, so
    `D > 0` means the fpu-alone/arb-off CANDIDATE won that deck; `D < 0` means
    the arb-on OPPONENT won it — this cell's PRIMARY question is which sign
    dominates."""
    return {s: (v[0] + v[1]) / 2.0
            for s, v in sorted(_by_deck(records).items()) if 0 in v and 1 in v}


def paired_margin(records: Iterable[Mapping]):
    """`(mean, z, n_paired, se, per_deck_list)`. `math.fsum` deliberately, not
    `sum`: a witness is a DIFFERENT computation from the one it checks."""
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
    return ((400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n_games)
            / (wr * (1 - wr)))


def elo_sigma_paired(wr: float, n_games: int) -> float:
    return elo_sigma_unpaired(wr, n_games) * PAIRING_FACTOR


#: ⭐⭐ AMENDED PRE-LAUNCH — the elo leg's PLANNING-TIME SE, resolved now that
#: `elo_sigma_paired` exists: `elo_sigma_paired(0.5, 800)` ≈ 8.686. This is the
#: elo-domain analogue of `SE_400` for the margin leg.
#: ⚠️⚠️ THE ORCHESTRATOR'S OWN AMENDMENT MESSAGE CITED "~±12 elo" FROM
#: CLAUDE.md's n-threshold table for "n=400 paired" — that table entry is
#: `elo_sigma_paired` at **400 GAMES** (200 decks paired): `elo_sigma_unpaired`
#: is a function of GAME count, not deck count, so 400 unpaired games (17 elo,
#: 1σ) × `PAIRING_FACTOR` ≈ 12. **This cell plays 800 GAMES** (400 decks × 2
#: seatings), not 400 — `elo_sigma_paired(0.5, 800)` ≈ 8.686, TIGHTER than the
#: ±12 the coordinator's message quoted, and it matches this exact cell shape's
#: own already-banked reference points to the third decimal
#: (`fpu_resurrection_CELL_FPU02` `elo_sigma=8.71`; `fpu_h2h` round 1
#: `elo_sigma=8.69` — both n=800). Verified rather than copied
#: (`feedback_verify_numbers_before_reporting`) — using the CORRECT, tighter
#: figure only strengthens the elo leg's case for being well-powered, so this
#: correction does not weaken the amendment's substance.
SE_ELO_PLANNING = elo_sigma_paired(0.5, N_GAMES_REAL_CELL)


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from raw records. CANDIDATE-referenced
    (a WIN for the candidate is `won_by_champ is True`, matching the harness's
    own `won_by_champ` field, which names the CANDIDATE `champ` regardless of
    which side of this cell's asymmetric config it plays)."""
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
            "elo_sig_1sigma_paired": sig_p, "elo_sig_1sigma_unpaired": sig_u,
            "elo_footing": "deck-paired", "elo_pairing_factor": PAIRING_FACTOR,
            "avg_diff": math.fsum(float(r["diff"]) for r in scored) / n}


def recon_close(a, b) -> bool:
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
    """`SIGMA_D_MODEL / sqrt(n)`. 400 decks -> ≈0.6905. POWER ARITHMETIC ONLY."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    modelled = se_model(n_decks)
    if (realized_se is None or (isinstance(realized_se, float) and math.isnan(realized_se))
            or modelled <= 0):
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True,
                "direction": "UNAVAILABLE (None or NaN realized SE — a "
                             "boundary win-rate, e.g., can make this "
                             "uncomputable; distinct from 'inside the band')",
                "note": "SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": not (lo <= ratio <= hi),
            "direction": ("TIGHTER than modelled" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)"
                          if ratio > hi else "inside the band"),
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


def elo_se_anomaly(realized_se: float | None, n_games: int = N_GAMES_REAL_CELL) -> dict:
    """⭐⭐ AMENDED PRE-LAUNCH — the elo leg's own version of `se_anomaly`, same
    treatment: MODELLED = the planning-time constant at the null footing
    (`elo_sigma_paired(0.5, n_games)`), REALIZED = the same formula fed the
    ACTUAL observed win rate (never a hand-picked or hardcoded number — it is
    `winrate_elo`'s own `elo_sig_1sigma_paired` field, i.e. genuinely realized
    from the cell's own records). Same `SE_ANOMALY_BAND` (0.70, 1.43), same
    "reported, never a branch input" discipline."""
    modelled = elo_sigma_paired(0.5, n_games)
    if (realized_se is None or (isinstance(realized_se, float) and math.isnan(realized_se))
            or modelled <= 0):
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True,
                "direction": "UNAVAILABLE (None or NaN realized SE — a "
                             "boundary win-rate, e.g., can make this "
                             "uncomputable; distinct from 'inside the band')",
                "note": "elo SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": not (lo <= ratio <= hi),
            "direction": ("TIGHTER than modelled" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)"
                          if ratio > hi else "inside the band"),
            "note": "ELO-DOMAIN DISPERSION ANOMALY — reported, never a branch input"}


def power_leg(delta: float, se: float, bar: float, z: float = HOLM_Z) -> dict:
    """`{p_killed, p_surprise}` for ONE leg at a true advantage `delta`, SE
    `se`, kill-bar `bar`, tested at threshold `z` (default `HOLM_Z`, the
    per-leg Holm-adjusted threshold; pass `BRANCH_Z` for the pre-amendment
    single-leg, uncorrected figure, kept only for side-by-side comparison).

    ⚠️ STATED HONESTLY (`feedback_verify_numbers_before_reporting` /
    `feedback_noisy_plateau_not_a_conclusion`): the LB95-style bound this
    design uses is a STRICTER (lower-power) test than a plain point-estimate
    threshold — `PREREG.md` §4.3 prints this table and does not round it up."""
    if se is None or se <= 0:
        return {"p_killed": float("nan"), "p_surprise": float("nan")}
    z_kill_thresh = (bar - delta) / se + z
    p_killed = 1.0 - _phi(z_kill_thresh)
    z_surprise_thresh = z + delta / se
    p_surprise = 1.0 - _phi(z_surprise_thresh)
    return {"p_killed": p_killed, "p_surprise": p_surprise}


def power_two_leg(delta_margin: float, delta_elo: float,
                  se_margin: float = SE_400, se_elo: float = SE_ELO_PLANNING) -> dict:
    """⭐⭐ AMENDED PRE-LAUNCH — the two-leg union power at true advantages
    `delta_margin` (pts/deck) and `delta_elo` (elo), both Holm-adjusted
    (`HOLM_Z`, per-leg).

    `SWAP-KILLED` fires if EITHER leg clears its Holm-adjusted bound (a union
    of two events over the SAME 800 games, so margin and elo are POSITIVELY
    CORRELATED — a game the fpu-alone candidate loses badly on points is
    disproportionately also a game it loses outright). This function does NOT
    know that correlation, so it reports the mathematically valid BRACKET
    instead of a false point estimate:

      * `p_killed_lower = max(p_killed_margin, p_killed_elo)` — the value
        reached in the limit of PERFECT positive correlation (the two legs
        fire on the same worlds, so the union adds nothing beyond the better
        leg);
      * `p_killed_upper = min(1, p_killed_margin + p_killed_elo)` — the
        union bound reached in the limit of INDEPENDENCE (no positive
        correlation at all).

    ⚠️ Say so explicitly: the true joint P(SWAP-KILLED) lies inside
    `[p_killed_lower, p_killed_upper]`, and because margin and elo are
    computed from the SAME game outcomes (positively correlated, not
    independent), the true value is expected to sit CLOSER TO THE LOWER
    BOUND than the upper one — i.e. Holm's assumption of independence, baked
    into `HOLM_Z`'s derivation, is CONSERVATIVE here (it under-states the true
    joint power slightly less than the upper bound would suggest, and more
    importantly it OVER-states the false-fire risk under a true null, which is
    the safe direction for a bar). The same bracket construction is applied to
    `p_surprise`."""
    m = power_leg(delta_margin, se_margin, BAR_SWAP)
    e = power_leg(delta_elo, se_elo, BAR_ELO_LEG)
    pk_lower = max(m["p_killed"], e["p_killed"])
    pk_upper = min(1.0, m["p_killed"] + e["p_killed"])
    ps_lower = max(m["p_surprise"], e["p_surprise"])
    ps_upper = min(1.0, m["p_surprise"] + e["p_surprise"])
    return {
        "leg_margin": m, "leg_elo": e,
        "p_killed_lower": pk_lower, "p_killed_upper": pk_upper,
        "p_surprise_lower": ps_lower, "p_surprise_upper": ps_upper,
        "p_unresolved_lower": max(0.0, 1.0 - pk_upper - ps_upper),
        "p_unresolved_upper": max(0.0, 1.0 - pk_lower - ps_lower),
        "correlation_note": "true joint P(SWAP-KILLED) is closer to the LOWER "
                            "bound than the upper — margin and elo are "
                            "positively correlated (same 800 games), and "
                            "the upper bound assumes independence, which "
                            "does not hold here.",
    }


# =========================================================================== #
# 4. THE BRANCH LADDER — PREREG.md §4 (AMENDED), pre-registered and EXHAUSTIVE #
# =========================================================================== #

BRANCHES = ("U-VOID-INSTRUMENT", "SWAP-KILLED", "SWAP-SURPRISE", "SWAP-UNRESOLVED")


def branch_for_cell(M, se_M, elo, se_elo, *, gates_ok: bool) -> str:
    """⭐⭐ AMENDED PRE-LAUNCH — TWO CO-PRIMARY LEGS, Holm-corrected, first
    match wins, in this EXACT order (`PREREG.md` §4, amended):

    `M` = candidate(fpu 0.2, arb-off) minus opponent(unmodified, arb-on B64),
    in points/deck (the harness's own `diff` sign, CANDIDATE minus OPPONENT);
    `se_M` its realized deck-paired SE (`paired_margin`'s own `se`, an
    empirical fsum-variance figure, never `SE_400`).
    `elo` = the candidate's deck-paired elo vs the opponent (`winrate_elo`'s
    `elo`, CANDIDATE-referenced — positive means the fpu-alone candidate is
    ahead); `se_elo` its REALIZED deck-paired SE (`winrate_elo`'s
    `elo_sig_1sigma_paired`, computed from the cell's OWN observed win rate —
    never `SE_ELO_PLANNING`, which is a planning-time constant at wr=0.5 and
    is reported only for the anomaly ratio, exactly as `SE_400`/
    `SIGMA_D_MODEL` are for the margin leg).

    `arb_advantage_margin := -M` (pts/deck), `arb_advantage_elo := -elo`
    (elo) — "how much the arb-on opponent beats the fpu-alone candidate by",
    on each leg's own scale.

      SWAP-KILLED     EITHER leg's `LB(arb_advantage) := arb_advantage_hat -
                       HOLM_Z*se >= <that leg's bar>`:
                         margin: `-M - HOLM_Z*se_M >= BAR_SWAP` (1.0 pts/deck)
                         elo:    `-elo - HOLM_Z*se_elo >= BAR_ELO_LEG` (15 elo)
                       i.e. `M + HOLM_Z*se_M <= -BAR_SWAP` OR
                            `elo + HOLM_Z*se_elo <= -BAR_ELO_LEG`.
      SWAP-SURPRISE   EITHER leg's `LB(candidate_side) := hat - HOLM_Z*se > 0`
                       (the fpu-alone candidate resolved CLEARLY ahead on
                       margin OR on elo):
                         margin: `M - HOLM_Z*se_M > 0`
                         elo:    `elo - HOLM_Z*se_elo > 0`
      SWAP-UNRESOLVED otherwise — see `power_two_leg` for the expected read
                       distribution at this n.

    ⛔⛔ CROSS-LEG DISAGREEMENT (a KILLED-eligible margin reading alongside a
    SURPRISE-eligible elo reading, or vice versa) is possible in principle —
    margin and elo are DIFFERENT statistics of the same 800 games, not
    identical ones, so nothing FORCES them to agree — even though it is not
    expected in practice (they are strongly positively correlated, and every
    `PRIOR_ART` row agrees in sign on both axes already). `SWAP-KILLED` is
    checked FIRST, so a genuine disagreement of this kind resolves to
    SWAP-KILLED, never to SWAP-SURPRISE. A real disagreement of this shape
    would itself be worth a RECON-class hand review before trusting the
    branch — the same posture `RIDERS_SWAP_SURPRISE` already takes toward a
    lone-branch reversal of a well-corroborated prior.

    ⛔ Within ONE leg, KILLED and SURPRISE remain mutually exclusive by the
    same construction as the pre-amendment single-leg ladder (a value that
    clears the negative KILLED threshold cannot also clear the positive
    SURPRISE threshold at the same, stricter `HOLM_Z`).

    ⚠️ NaN GUARD (found while testing against the real tiny fixture, whose
    tiny n hit `wr=0.0` exactly — a boundary `winrate_elo` cannot compute a
    finite SE for): a leg whose `se` is `None` **or `nan`** (or `<= 0`, a
    degenerate variance) ABSTAINS from firing either of ITS OWN branches —
    it is treated as uninformative, not as forcing a void, because the OTHER
    leg may still be perfectly healthy and there is no principled reason a
    boundary win-rate on 800 games should silence a clean margin reading.
    `U-VOID-INSTRUMENT` fires only if BOTH legs are unusable (`None`/`nan`/
    non-positive `se` on both, or a missing point estimate on both) — at that
    point there is no reading of any kind, on either axis, and this is the
    same "ABSENT is FAIL" posture the rest of this pair uses, extended to
    "both legs ABSENT/unusable is FAIL" rather than "any one field ABSENT is
    FAIL", because this function now has two independent sources of signal.
    """
    if not gates_ok:
        return "U-VOID-INSTRUMENT"

    def _leg(hat, se, bar):
        """`(usable, killed, surprise)` for one leg. `usable=False` means this
        leg abstains — its `killed`/`surprise` are always `False`."""
        if hat is None or se is None or (isinstance(se, float) and math.isnan(se)) or se <= 0:
            return False, False, False
        return True, (hat + HOLM_Z * se) <= -bar, (hat - HOLM_Z * se) > 0.0

    m_usable, margin_killed, margin_surprise = _leg(M, se_M, BAR_SWAP)
    e_usable, elo_killed, elo_surprise = _leg(elo, se_elo, BAR_ELO_LEG)
    if not (m_usable or e_usable):
        return "U-VOID-INSTRUMENT"
    if margin_killed or elo_killed:
        return "SWAP-KILLED"
    if margin_surprise or elo_surprise:
        return "SWAP-SURPRISE"
    return "SWAP-UNRESOLVED"


RIDERS_ALWAYS = (
    "⛔ SELF-ANCHORED: every statistic here is THIS candidate/opponent pair on "
    "THIS band, not absolute strength. No prior or later round is pooled.",
    "⛔ NEITHER LEG'S BAR (margin +1.0 pts/deck, elo +15) IS THE DECISION-"
    "RELEVANT BAR PER SE — the arbiter's own clock cost (~+2 elo ≈ ~0.35 "
    "pts/deck) is, and that remains UNRESOLVABLE at n=400/800 on EITHER leg "
    "alone (SE_400≈0.69 pts/deck, SE_ELO_PLANNING≈8.69 elo both exceed it). "
    "Both bars are AFFORDABLE reads at a decision-anchored multiple of that "
    "cost (margin ≈3× the refund in points-gloss terms, elo ≈7× the refund "
    "directly) — the KILL direction at a resolution this design can see, not "
    "a re-derivation of the 0.35 figure itself.",
    "⛔ This round makes NO source change and licenses NO PRODUCTION.yaml "
    "change on any branch — SWAP-KILLED confirms the existing declined-by-"
    "arithmetic posture; SWAP-SURPRISE or SWAP-UNRESOLVED name a re-open "
    "candidate for a LATER, freshly funded round, never an automatic action.",
    "⭐ HOLM CORRECTION: both legs' bars are tested at `HOLM_Z≈2.278`, not the "
    "pre-amendment `BRANCH_Z=2.0` — the per-leg threshold is STRICTER because "
    "two legs are now tested instead of one, holding the family-wise false-"
    "fire rate at the original single-leg level.",
)
RIDERS_SWAP_KILLED = (
    "The direct read agrees with the arithmetic: the arb side's advantage "
    "resolves above the affordable bar on at least one CO-PRIMARY leg. "
    "docs/LEVER_INDEX.md's declined-by-arithmetic row should be updated to "
    "CONFIRMED-BY-DIRECT-READ, not reopened. State WHICH leg(s) fired — a "
    "margin-only fire and an elo-only fire are both valid SWAP-KILLED reads "
    "but are different evidence and should be reported as such, not merged "
    "into one undifferentiated line.",
)
RIDERS_SWAP_SURPRISE = (
    "⚠️⚠️ THIS WOULD CONTRADICT EVERY PRIOR ARM OF THIS AXIS (fpu-alone +2.95, "
    "arb-alone +5.21/+66/+69, fpu-on-arb +1.02/+0.86 — all pointing arb-side-"
    "positive). RECON and every gate must be re-checked by hand before this "
    "branch is trusted; a single-cell reversal of a well-corroborated prior is "
    "the textbook noise-signature case (feedback_noisy_plateau_not_a_conclusion, "
    "feedback_results_table_source_of_truth). If only ONE leg fired SURPRISE "
    "while the other leg's point estimate still points arb-favoring, that "
    "CROSS-LEG DISAGREEMENT (branch_for_cell's own docstring) is itself the "
    "first thing to review, before the branch label.",
)
RIDERS_SWAP_UNRESOLVED = (
    "This is the branch the pre-amendment margin-only ladder's own arithmetic "
    "predicted was most probable at n=400 — but with the elo leg added "
    "(power_two_leg table, PREREG §4.3), a true elo gap near the funding "
    "brief's own ~+40 prior makes SWAP-KILLED the MODAL branch instead. An "
    "unresolved read here, after the amendment, is a genuinely more surprising "
    "outcome than it was in the margin-only design — worth a second look at "
    "the realized se_anomaly on BOTH legs before accepting it at face value.",
)


# =========================================================================== #
# 5. THE ASYMMETRIC-ARBITER GATES — the reason this round exists              #
# =========================================================================== #

def arb_asymmetry_gate(manifest: Mapping) -> dict:
    """`G-ARB-ASYM` — candidate ABSENT, opponent ARMED at the deployed spec.
    Thin wrapper over `tiearb_gates.assert_tiearb_sides` so this pair and the
    module it cites cannot drift apart."""
    ok, findings = TA.check_tiearb_sides(manifest, cand_expected=None,
                                         opp_expected=DEPLOYED_TIEARB)
    return gate("G-ARB-ASYM", ok, {"findings": findings},
               "manifest cand_tiearb / opp_tiearb (see tiearb_gates.py)",
               ("candidate UNARMED, opponent ARMED at the deployed B=64 spec — "
                "exactly the intended asymmetry" if ok else
                "⛔ G-ARB-ASYM FAILED: " + "; ".join(findings)))


def arb_fired_gate(summary: Mapping) -> dict:
    """`G-ARB-FIRED` — the POSITIVE CONTROL half of the asymmetry: a config gate
    proves the arbiter was REQUESTED on the opponent seat; this proves it BOUND
    and BIT (`tiearb_gates.tiearb_sides_summary`'s realized fire counters), not
    merely a healthy-looking dict that never actually arbitrated a tie."""
    sides = TA.tiearb_sides_summary(summary or {})
    opp = sides.get("opponent")
    cand = sides.get("candidate")
    bad = []
    if opp is None:
        bad.append("opp_tiearb_games ABSENT/zero — the opponent's arbiter "
                   "container was never exercised in PLAY, config gate "
                   "notwithstanding")
    elif not opp.get("fired_plies"):
        bad.append(f"opp_tiearb fired_plies is {opp.get('fired_plies')!r} — "
                   "requested but never actually fired on a single tied ply")
    if cand is not None and (cand.get("fired_plies") or 0) > 0:
        bad.append(f"⛔ the CANDIDATE'S arbiter ALSO fired ({cand}) — the "
                   "candidate seat is not unarmed in PLAY, whatever the config "
                   "gate says")
    ok = not bad
    return gate("G-ARB-FIRED", ok, {"candidate": cand, "opponent": opp},
               "summary.json opp_tiearb_*/tiearb_* (tiearb_sides_summary)",
               ("the opponent's arbiter fired on a nonzero count of tied plies "
                "and the candidate's did not fire at all" if ok else
                "⛔ G-ARB-FIRED FAILED: " + "; ".join(bad)))


def fpu_knob_gate(manifest: Mapping) -> dict:
    """`G-FPU` — the candidate REQUESTED `fpu_reduction=0.2` (the harness's own
    request-side field, `config.cand_search.fpu_reduction`). Carried from
    `fpu_resurrection_prep.knob_gate` in spirit, simplified to this cell's
    single frozen dose (no c_puct axis here)."""
    d = {"manifest": manifest or {}}
    requested, addr = resolve(d, "manifest:config.cand_search.fpu_reduction")
    bad = []
    if requested is MISSING:
        bad.append("config.cand_search.fpu_reduction ABSENT — ABSENT is FAIL. "
                   "A harness predating the fpu plumbing (2026-08-29) cannot "
                   "be adjudicated: its candidate is fpu-blind by construction.")
    elif requested is None or float(requested) != FPU_DOSE:
        bad.append(f"fpu_reduction is {requested!r}, this cell is frozen at "
                   f"{FPU_DOSE!r}")
    return gate("G-FPU", not bad,
                {"requested_fpu_reduction": None if requested is MISSING
                                            else requested, "frozen": FPU_DOSE},
                addr, ("the REQUEST matches the frozen dose" if not bad
                       else "⛔ G-FPU FAILED: " + "; ".join(bad)))


def fpu_twosided_gate(manifest: Mapping) -> dict:
    """`G-FPU-TWOSIDED` — the SECOND witness: the RESOLVED config of each side
    (not merely the request) proves the dose bound on the CANDIDATE and NOWHERE
    ELSE. `config.opponent.champ_cfg.fpu_reduction` must read an explicit
    `null` — a healthy archive states the opponent's value POSITIVELY."""
    d = {"manifest": manifest or {}}
    cv, ca = resolve(d, "manifest:config.champion.fpu_reduction")
    ov, oa = resolve(d, "manifest:config.opponent.champ_cfg.fpu_reduction",
                     "manifest:config.opponent.fpu_reduction")
    bad = []
    if cv is MISSING:
        bad.append("config.champion.fpu_reduction ABSENT — ABSENT is FAIL")
    elif cv is None or float(cv) != FPU_DOSE:
        bad.append(f"the candidate's RESOLVED fpu_reduction is {cv!r}, not the "
                   f"frozen {FPU_DOSE!r} — the knob did NOT bind")
    if ov is MISSING:
        bad.append("config.opponent.champ_cfg.fpu_reduction ABSENT — ABSENT is "
                   "FAIL (the opponent must state its value POSITIVELY)")
    elif ov is not None:
        bad.append(f"⛔ the OPPONENT carries fpu_reduction={ov!r} — it is not "
                   "the unmodified champion")
    return gate("G-FPU-TWOSIDED", not bad,
                {"champion_resolved": None if cv is MISSING else cv,
                 "opponent_resolved": None if ov is MISSING else ov},
                ca or oa,
                ("the dose bound on the candidate's resolved config and the "
                 "opponent carries the champion's unmodified value" if not bad
                 else "⛔ G-FPU-TWOSIDED FAILED: " + "; ".join(bad)))


# =========================================================================== #
# 6. SELF-CHECK — the library's own invariants                                #
# =========================================================================== #

#: A "neutral" reading on one leg — exactly at its own null, wide enough SE
#: that it never independently fires either branch — so sanity_check's
#: single-leg sweeps below isolate the OTHER leg's behavior.
_NEUTRAL_M, _NEUTRAL_SE_M = 0.0, SE_400
_NEUTRAL_ELO, _NEUTRAL_SE_ELO = 0.0, SE_ELO_PLANNING


def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean."""
    p: list[str] = []
    if abs(se_model(400) - SE_400) > 1e-9:
        p.append("SE_400 constant disagrees with se_model(400)")
    if not (0.0 < BAR_SWAP < 5.0):
        p.append(f"BAR_SWAP {BAR_SWAP} is outside a sane range")
    if not (0.0 < BAR_ELO_LEG < 200.0):
        p.append(f"BAR_ELO_LEG {BAR_ELO_LEG} is outside a sane range")
    if DEPLOYED_TIEARB != TA.DEPLOYED_TIEARB_B64:
        p.append("DEPLOYED_TIEARB has drifted from tiearb_gates.DEPLOYED_TIEARB_B64")
    if K_DETS * SIMS_PER_DET != TOTAL_SIMS:
        p.append(f"{K_DETS} x {SIMS_PER_DET} != {TOTAL_SIMS}")
    # --- AMENDED PRE-LAUNCH: HOLM_Z / SE_ELO_PLANNING self-consistency -------
    if abs(SE_ELO_PLANNING - elo_sigma_paired(0.5, N_GAMES_REAL_CELL)) > 1e-9:
        p.append("SE_ELO_PLANNING constant disagrees with "
                 "elo_sigma_paired(0.5, N_GAMES_REAL_CELL)")
    recomputed_holm_z = _phi_inv(1.0 - (1.0 - _phi(BRANCH_Z)) / 2.0)
    if abs(HOLM_Z - recomputed_holm_z) > 1e-6:
        p.append(f"HOLM_Z {HOLM_Z} disagrees with its own re-derivation "
                 f"{recomputed_holm_z}")
    if not (HOLM_Z > BRANCH_Z):
        p.append(f"HOLM_Z {HOLM_Z} is not stricter than BRANCH_Z {BRANCH_Z} — "
                 "a 2-leg correction must raise the per-leg bar, not lower it")
    if not (2.0 < HOLM_Z < 2.6):
        p.append(f"HOLM_Z {HOLM_Z} is outside the expected ~2.2-2.4 range for "
                 "an m=2 Holm correction off BRANCH_Z=2.0 — check the derivation")
    # `_phi`/`_phi_inv` round-trip at a handful of points
    for x in (-2.5, -1.0, 0.0, 1.0, 2.2776, 3.0):
        rt = _phi_inv(_phi(x))
        if abs(rt - x) > 1e-4:
            p.append(f"_phi_inv(_phi({x})) = {rt}, not a clean round-trip")

    # --- branch ladder: type + exhaustiveness, swept over a 2D grid ----------
    for m10 in range(-600, 601, 30):
        M = m10 / 100.0
        for e10 in range(-6000, 6001, 600):
            elo = e10 / 10.0
            b = branch_for_cell(M, SE_400, elo, SE_ELO_PLANNING, gates_ok=True)
            if b not in BRANCHES:
                p.append(f"branch_for_cell(M={M},elo={elo}) returned unknown {b!r}")
            # re-derive independently and cross-check (a witness, not a copy)
            m_killed = (M + HOLM_Z * SE_400) <= -BAR_SWAP
            e_killed = (elo + HOLM_Z * SE_ELO_PLANNING) <= -BAR_ELO_LEG
            m_surprise = (M - HOLM_Z * SE_400) > 0.0
            e_surprise = (elo - HOLM_Z * SE_ELO_PLANNING) > 0.0
            expect = ("SWAP-KILLED" if (m_killed or e_killed) else
                      "SWAP-SURPRISE" if (m_surprise or e_surprise) else
                      "SWAP-UNRESOLVED")
            if b != expect:
                p.append(f"branch_for_cell(M={M},elo={elo}) = {b}, "
                         f"independent re-derivation says {expect}")

    # --- single-leg isolation: each leg alone must be able to fire each branch
    if branch_for_cell(-10.0, 0.3, _NEUTRAL_ELO, _NEUTRAL_SE_ELO,
                       gates_ok=True) != "SWAP-KILLED":
        p.append("margin leg alone: a strongly negative M did not fire SWAP-KILLED")
    if branch_for_cell(10.0, 0.3, _NEUTRAL_ELO, _NEUTRAL_SE_ELO,
                       gates_ok=True) != "SWAP-SURPRISE":
        p.append("margin leg alone: a strongly positive M did not fire SWAP-SURPRISE")
    if branch_for_cell(_NEUTRAL_M, _NEUTRAL_SE_M, -100.0, 3.0,
                       gates_ok=True) != "SWAP-KILLED":
        p.append("elo leg alone: a strongly negative elo did not fire SWAP-KILLED")
    if branch_for_cell(_NEUTRAL_M, _NEUTRAL_SE_M, 100.0, 3.0,
                       gates_ok=True) != "SWAP-SURPRISE":
        p.append("elo leg alone: a strongly positive elo did not fire SWAP-SURPRISE")
    if branch_for_cell(_NEUTRAL_M, _NEUTRAL_SE_M, _NEUTRAL_ELO, _NEUTRAL_SE_ELO,
                       gates_ok=True) != "SWAP-UNRESOLVED":
        p.append("both legs neutral did not read SWAP-UNRESOLVED")

    # --- cross-leg disagreement resolves to SWAP-KILLED (checked first) ------
    disagree = branch_for_cell(-10.0, 0.3, 100.0, 3.0, gates_ok=True)
    if disagree != "SWAP-KILLED":
        p.append(f"a margin-KILLED / elo-SURPRISE disagreement read {disagree!r}, "
                 "not SWAP-KILLED (branch_for_cell must check KILLED first)")

    # --- void conditions ---------------------------------------------------
    if branch_for_cell(-1.5, SE_400, -40.0, SE_ELO_PLANNING,
                       gates_ok=False) != "U-VOID-INSTRUMENT":
        p.append("gates_ok=False did not force U-VOID-INSTRUMENT")
    # BOTH legs missing/unusable -> VOID
    for args in ((None, SE_400, None, SE_ELO_PLANNING),
                (0.0, None, 0.0, None),
                (0.0, float("nan"), 0.0, float("nan")),
                (None, None, None, None)):
        if branch_for_cell(*args, gates_ok=True) != "U-VOID-INSTRUMENT":
            p.append(f"both legs unusable {args} did not force U-VOID-INSTRUMENT")
    # ⚠️ ONE leg missing/unusable but the OTHER healthy -> NOT void, the
    # healthy leg still decides (the NaN-guard's whole point — a boundary
    # win-rate on one leg must not silence a clean reading on the other).
    if branch_for_cell(None, None, -40.0, SE_ELO_PLANNING,
                       gates_ok=True) != "SWAP-KILLED":
        p.append("margin leg missing, elo leg healthy+killed: did not read "
                 "SWAP-KILLED off the elo leg alone")
    if branch_for_cell(-1.5, SE_400, None, float("nan"),
                       gates_ok=True) != "SWAP-UNRESOLVED":
        p.append("elo leg missing, margin leg healthy-but-unresolved: did not "
                 "read SWAP-UNRESOLVED off the margin leg alone")

    # --- power_leg / power_two_leg arithmetic ---------------------------
    pl = power_leg(FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR, SE_400, BAR_SWAP)
    if not (0.0 <= pl["p_killed"] <= 1.0 and 0.0 <= pl["p_surprise"] <= 1.0):
        p.append(f"power_leg returned out-of-range probabilities: {pl}")
    pl_bigger = power_leg(ARITHMETIC_RECONSTRUCTION_ARB_ADVANTAGE, SE_400, BAR_SWAP)
    if pl_bigger["p_killed"] < pl["p_killed"]:
        p.append("power_leg(SWAP-KILLED) is not monotone increasing in the "
                 "true arb advantage (margin leg)")
    pw2 = power_two_leg(FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR, 40.0)
    if not (pw2["p_killed_lower"] <= pw2["p_killed_upper"] + 1e-9):
        p.append(f"power_two_leg bounds inverted: {pw2}")
    if not (pw2["p_killed_lower"] >= max(pw2["leg_margin"]["p_killed"],
                                         pw2["leg_elo"]["p_killed"]) - 1e-9):
        p.append("power_two_leg's p_killed_lower is not the max of the two legs")
    # the elo leg alone should dominate under the funding brief's elo prior —
    # this is the whole point of the amendment; a regression here means the
    # amendment silently stopped doing what it was built to do.
    if pw2["leg_elo"]["p_killed"] <= pw2["leg_margin"]["p_killed"]:
        p.append("under the funding-brief priors (margin +1.5 / elo +40), the "
                 "elo leg's P(killed) is not bigger than the margin leg's — "
                 "the amendment's own premise (elo is the better-powered axis) "
                 "does not hold with these constants; check BAR_ELO_LEG/"
                 "SE_ELO_PLANNING/HOLM_Z")
    return p
