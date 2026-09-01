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

#: `RECON` tolerance.
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

PAIRING_FACTOR = 1.0 / math.sqrt(2.0)          #: ≈ 0.70711
BAR_ELO = 400.0 / math.log(10) * BAR_SWAP      #: NEVER a branch input — see below.
#: ⚠️ `BAR_ELO` above is a LINEARIZED gloss (elo ≈ 173*points at wr≈0.5) for
#: human-scale comparison ONLY, exactly as `tiearb_widening`'s "23 elo" gloss was
#: — "the gloss adjudicates nothing (one band, one cell, elo is nonlinear in
#: win-rate)". No branch anywhere reads it.

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
                "-40 elo' for the swap — i.e. an arb-side advantage on the "
                "order of a few tens of elo, ~1-1.5 pts/deck by the same "
                "linearized gloss BAR_ELO uses. This cell is the DIRECT "
                "measurement the arithmetic stood in for.",
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


def power_at(true_arb_advantage: float, se: float, bar: float = BAR_SWAP) -> dict:
    """`{p_killed, p_surprise, p_unresolved}` at a true `arb_advantage = -M`.

    ⚠️ STATED HONESTLY (`feedback_verify_numbers_before_reporting` /
    `feedback_noisy_plateau_not_a_conclusion`): the LB95-style bound this
    round's `BAR_SWAP` test uses is a STRICTER (lower-power) test than a plain
    point-estimate threshold. Even at the funding brief's own prior
    (`+1.5 pts/deck`) power for `SWAP-KILLED` is well under 50% at n=400 —
    `SWAP-UNRESOLVED` is the single MOST PROBABLE branch under either prior in
    `PRIOR_ART`. `PREREG.md` §4.2 prints this table and does not round it up."""
    if se is None or se <= 0:
        return {"p_killed": float("nan"), "p_surprise": float("nan"),
                "p_unresolved": float("nan")}
    delta = true_arb_advantage
    z_kill_thresh = (bar - delta) / se + BRANCH_Z
    p_killed = 1.0 - _phi(z_kill_thresh)
    z_surprise_thresh = BRANCH_Z + delta / se
    p_surprise = 1.0 - _phi(z_surprise_thresh)
    p_unresolved = max(0.0, 1.0 - p_killed - p_surprise)
    return {"p_killed": p_killed, "p_surprise": p_surprise,
            "p_unresolved": p_unresolved}


# =========================================================================== #
# 4. THE BRANCH LADDER — PREREG.md §4, pre-registered and EXHAUSTIVE          #
# =========================================================================== #

BRANCHES = ("U-VOID-INSTRUMENT", "SWAP-KILLED", "SWAP-SURPRISE", "SWAP-UNRESOLVED")


def branch_for_cell(M, se, *, gates_ok: bool) -> str:
    """First match wins, in this EXACT order (`PREREG.md` §4).

    `M` = candidate(fpu 0.2, arb-off) minus opponent(unmodified, arb-on B64),
    in points/deck (the harness's own `diff` sign, CANDIDATE minus OPPONENT).
    `arb_advantage := -M` is "how many points/deck the arb-on opponent beats
    the fpu-alone candidate by".

      SWAP-KILLED     `LB95(arb_advantage) = -M - 2*se >= BAR_SWAP`
                       i.e. `M + 2*se <= -BAR_SWAP`  (UB95(M) at or below
                       -1.0 pts/deck — the arb side's advantage is resolved
                       CLEARLY above the bar)
      SWAP-SURPRISE   `LB95(M) = M - 2*se > 0`  (the fpu-alone, arb-off
                       candidate's advantage is resolved CLEARLY positive —
                       i.e. arb_advantage's UB95 < 0)
      SWAP-UNRESOLVED otherwise — includes every case where the sign is right
                       but not resolved past the bar, exactly the branch the
                       funding brief's own arithmetic (`PRIOR_ART`) predicts is
                       most probable at this n (see `power_at`).

    ⛔ Mutually exclusive by construction: `SWAP-KILLED` requires
    `M <= -BAR_SWAP - 2*se < 0`, which forces `LB95(M) = M - 2*se <=
    -BAR_SWAP - 4*se < 0`, so it can never ALSO satisfy `SWAP-SURPRISE`.
    """
    if not gates_ok:
        return "U-VOID-INSTRUMENT"
    if M is None or se is None:
        return "U-VOID-INSTRUMENT"
    ub95_m = M + 2.0 * se
    lb95_m = M - 2.0 * se
    if ub95_m <= -BAR_SWAP:
        return "SWAP-KILLED"
    if lb95_m > 0.0:
        return "SWAP-SURPRISE"
    return "SWAP-UNRESOLVED"


RIDERS_ALWAYS = (
    "⛔ SELF-ANCHORED: every statistic here is THIS candidate/opponent pair on "
    "THIS band, not absolute strength. No prior or later round is pooled.",
    "⛔ BAR_SWAP (+1.0 pts/deck) is NOT the decision-relevant bar — the "
    "arbiter's own clock cost (~0.35 pts/deck) is, and that is UNRESOLVABLE at "
    "n=400 (SE_400 ≈ 0.69 alone exceeds it). BAR_SWAP is the affordable KILL "
    "direction only.",
    "⛔ This round makes NO source change and licenses NO PRODUCTION.yaml "
    "change on any branch — SWAP-KILLED confirms the existing declined-by-"
    "arithmetic posture; SWAP-SURPRISE or SWAP-UNRESOLVED name a re-open "
    "candidate for a LATER, freshly funded round, never an automatic action.",
)
RIDERS_SWAP_KILLED = (
    "The direct read agrees with the arithmetic: the arb side's clock cost is "
    "affordable and its strength margin over the fpu-alone swap resolves above "
    "the affordable bar. docs/LEVER_INDEX.md's declined-by-arithmetic row "
    "should be updated to CONFIRMED-BY-DIRECT-READ, not reopened.",
)
RIDERS_SWAP_SURPRISE = (
    "⚠️⚠️ THIS WOULD CONTRADICT EVERY PRIOR ARM OF THIS AXIS (fpu-alone +2.95, "
    "arb-alone +5.21/+66/+69, fpu-on-arb +1.02/+0.86 — all pointing arb-side-"
    "positive). RECON and every gate must be re-checked by hand before this "
    "branch is trusted; a single-cell reversal of a well-corroborated prior is "
    "the textbook noise-signature case (feedback_noisy_plateau_not_a_conclusion, "
    "feedback_results_table_source_of_truth).",
)
RIDERS_SWAP_UNRESOLVED = (
    "This is the branch the funding brief's own arithmetic predicts is most "
    "probable at n=400 (power_at table, PREREG §4.2) — an unresolved read here "
    "is NOT evidence against the arb side; it is the expected outcome of an "
    "underpowered direct measurement of an already-strongly-primed direction.",
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

def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean."""
    p: list[str] = []
    if abs(se_model(400) - SE_400) > 1e-9:
        p.append("SE_400 constant disagrees with se_model(400)")
    if not (0.0 < BAR_SWAP < 5.0):
        p.append(f"BAR_SWAP {BAR_SWAP} is outside a sane range")
    if DEPLOYED_TIEARB != TA.DEPLOYED_TIEARB_B64:
        p.append("DEPLOYED_TIEARB has drifted from tiearb_gates.DEPLOYED_TIEARB_B64")
    if K_DETS * SIMS_PER_DET != TOTAL_SIMS:
        p.append(f"{K_DETS} x {SIMS_PER_DET} != {TOTAL_SIMS}")
    # branch ladder mutual exclusivity, swept numerically
    for m10 in range(-600, 601, 3):
        M = m10 / 100.0
        for se10 in (10, 30, 50, 69, 90, 140):
            se = se10 / 100.0
            b = branch_for_cell(M, se, gates_ok=True)
            if b not in BRANCHES:
                p.append(f"branch_for_cell({M},{se}) returned unknown {b!r}")
    # a healthy pair of extreme M values must land on opposite non-null branches
    if branch_for_cell(-10.0, 0.3, gates_ok=True) != "SWAP-KILLED":
        p.append("a strongly negative M (arb side crushing) did not read SWAP-KILLED")
    if branch_for_cell(10.0, 0.3, gates_ok=True) != "SWAP-SURPRISE":
        p.append("a strongly positive M (fpu side crushing) did not read SWAP-SURPRISE")
    if branch_for_cell(0.0, 0.69, gates_ok=True) != "SWAP-UNRESOLVED":
        p.append("M=0 did not read SWAP-UNRESOLVED")
    if branch_for_cell(-1.5, 0.69, gates_ok=False) != "U-VOID-INSTRUMENT":
        p.append("gates_ok=False did not force U-VOID-INSTRUMENT")
    if branch_for_cell(None, None, gates_ok=True) != "U-VOID-INSTRUMENT":
        p.append("missing M/se did not force U-VOID-INSTRUMENT")
    # power_at sums to 1 and is monotone-ish in the killed direction
    pw = power_at(FUNDING_BRIEF_ARB_ADVANTAGE_PRIOR, SE_400)
    total = pw["p_killed"] + pw["p_surprise"] + pw["p_unresolved"]
    if abs(total - 1.0) > 1e-6:
        p.append(f"power_at branches do not sum to 1 ({total})")
    pw_bigger = power_at(ARITHMETIC_RECONSTRUCTION_ARB_ADVANTAGE, SE_400)
    if pw_bigger["p_killed"] < pw["p_killed"]:
        p.append("power_at(SWAP-KILLED) is not monotone increasing in the true "
                 "arb advantage")
    return p
