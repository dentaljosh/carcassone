"""`screen_lib_g3` — THE LAW OF S1 GATE G3 (the three-arm decomposition cell).

⛔ **THE PAIR IS LAW.** [`DESIGN.md`](DESIGN.md) §6.4 + [`READ_RULE_G3.md`](READ_RULE_G3.md).
If this file disagrees with them, **it is this file that is wrong.**

⛔ **NOTHING HERE HAS BEEN RUN AGAINST A REAL CELL. 0 games exist.**

This module is imported by BOTH `run_g3.sh`'s precondition ladder and
`analyze_g3.py`, so a launcher/adjudicator drift is impossible by construction
rather than by review. Every constant, cell shape, band, bar and branch lives
here exactly once.

⚠️ **Module name.** It is `screen_lib_g3`, not `screen_lib`, deliberately:
`measurement/phasegate_prep/` and `measurement/fpu_resurrection_prep/` both ship
a `screen_lib.py` and the collision cost a 21-failure suite on 2026-08-30 (R2).
A name that cannot collide cannot be shadowed.
"""
from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

# =========================================================================== #
# 0. THE INSTRUMENT'S FROZEN CONSTANTS                                         #
# =========================================================================== #

#: ⭐ ONE band. DESIGN §6.4 and SIZING §6 require ONE SHARED DECK SET across the
#: three arms — P2 (`margin(OPP) − margin(OWN)`) is a CROSS-ARM contrast and CRN
#: is what makes it a statistic rather than two independent draws.
BAND = 161_000_000_000

#: The smoke's sub-range. ⛔ NEVER part of the claim; excluded from adjudication
#: by the `SMOKE_` prefix.
THROWAWAY_BASE = 161_999_999_000
THROWAWAY_SPAN = 1000

#: ⭐ THE INVERTED HASH GATE. Surfaces B/C move NO leaf hash, so a cell's
#: `cand_leaf_hash` must **EQUAL** the champion's; a MOVED hash means a leaf
#: change was smuggled in (READ_RULE_G1 §5.2, carried verbatim).
LEAF_HASH = "a36d2e15a3b3d71d"

#: Budget, BOTH sides — `PRODUCTION.yaml` `fair_deploy`, the 2026-08-30 promoted
#: desktop champion. Re-asserted against the YAML at launch (`G-PROD`).
K_DETS = 16
SIMS_PER_DET = 1376
TOTAL_SIMS = 22016

EXACT_K = 2
EXACT_MODE = "marginalized"
BACKEND = "rust"
RULES_PROFILE = "fixed_v1"

#: ⭐⭐ THE SINGLE VARIABLE. Dose and mask are IDENTICAL across the three arms;
#: `scope` is the only thing that moves. Dose 0.25 is `d*` from
#: [`G1_VERDICT.md`](G1_VERDICT.md) — the SMALLEST OBSERVABLE dose, and
#: expression is not effect (READ_RULE_G1 §6.5).
JR_DOSE = 0.25
#: Mask 31 == the frozen `joshua_bot.PRESETS["current"]` J bundle, per the
#: owner's adopted answer to DESIGN §11 Q2. A J2-only mask is the licensed
#: follow-on, not an arm of this cell.
JR_MASK = 31

SCOPES = ("opp", "own", "all")


# --------------------------------------------------------------------------- #
# 0.1 THE STATISTICAL MODEL — every number traced to a REALIZED artifact        #
# --------------------------------------------------------------------------- #
# ⛔ POWER ARITHMETIC ONLY. No branch test uses a MODELLED se as its denominator;
# every branch reads the cell's OWN REALIZED se (§5). These exist so the
# pre-outcome bars are arithmetic rather than vibes, and so a realized se far
# from the model is FLAGGED instead of silently believed.

#: Deck-paired margin sem at n=800 games (400 decks x 2 seatings), deploy budget.
#: SIZING §1 I4: 0.6214 (`jpriors_d0p5_…`) and 0.6460 (`jrules_d0p25_…`) in
#: `experiments/results.csv`. SIZING §4 rounds the pair to 0.63.
SEM_800 = 0.63

#: Per-DECK sd implied by SEM_800 at 400 decks: 0.63 * sqrt(400).
SIGMA_D_MODEL = SEM_800 * math.sqrt(400.0)          # == 12.6

#: 1σ elo at n=800 on the DECK-PAIRED footing. SIZING §1 I5, from the same two
#: `results.csv` rows: 12.285 / 12.343.
SIGMA_ELO_800 = 12.285

#: ⚠️⚠️ THE HOUSE THUMB-RULE IS ~1.4x OPTIMISTIC AGAINST THIS INSTRUMENT, and it
#: is stated here rather than discovered in a readout. CLAUDE.md's results
#: discipline gives "n=400 → 1σ ≈ ±17 elo unpaired; deck-PAIRING ~halves variance
#: → n=400 paired ≈ ±12 elo", which extrapolates to ~8.7 elo at n=800. The
#: REALIZED paired 1σ at n=800 in this exact instrument class is **12.285** —
#: i.e. the realized pairing gain is materially weaker than the thumb-rule's
#: assumed factor of 2 on the variance. ⛔ THE FROZEN σ BELOW ARE THE REALIZED
#: ONES, scaled 1/sqrt(n). The thumb-rule is recorded as context and is NOT used.
HOUSE_THUMB_ELO_400_PAIRED = 12.0

#: P2's cross-arm correlation. ⛔ FROZEN AT THE CONSERVATIVE VALUE (SIZING §4):
#: the two arms are already deck-paired within themselves, so the residual
#: correlation comes only from the shared champion play. ρ=0 is the pessimistic
#: assumption and is what the pre-outcome bar is stated on. The REALIZED ρ is
#: computed from the shared decks at adjudication and REPORTED — it never moves
#: the frozen bar, but the branch reads the REALIZED se of D (§5), which prices
#: the true correlation automatically.
RHO_FROZEN = 0.0

#: ⭐⭐ HOLM, two-sided, family α = 0.05 over the DUAL PRIMARY {P1, P2}
#: (DESIGN §6.4, "the c1_pricing_prep precedent"). Step-down: the LARGER |z| is
#: tested at α/2, the smaller at α; a failure at step 1 stops the ladder.
#:   z(α/2 = 0.025 two-sided) = 2.2414 ;  z(α = 0.05 two-sided) = 1.9600
#: DESIGN's branch map writes the shorthand "≥ +2σ"; 2.0 sits INSIDE this
#: bracket, so the ladder is the operative rule and the shorthand is honoured by
#: the correction DESIGN itself names. Derived at freeze, pre-outcome.
HOLM_Z = (2.2414, 1.9600)
#: The nominal per-leg 2σ, reported beside every branch so a marginal case is
#: visible rather than arbitrated. ⛔ NOT the branch rule.
NOMINAL_Z = 2.0

#: `N4-COST` (DESIGN §6.4): the house budget-confound trigger on
#: `ms_ratio_cand_over_opp`. SIZING §3 predicts 1.078–1.085 for `opp`.
#: ⛔ A RIDER, never a void: surface A's realized 1.2116 is what downgraded that
#: cell's loss to "confounded by budget", and this cell must be able to say the
#: same about itself.
N4_MS_RATIO_TRIGGER = 1.20

#: `N5-FAIL` (DESIGN §6.4): any failed game / stranded claim voids per IS-A1.
FAILURE_RATE_VOID = 0.0

#: Companion rails. ⛔ REPORTED, NEVER BRANCH INPUTS.
SAT_BAND = (0.35, 0.65)
SE_ANOMALY_BAND = (0.70, 1.43)
#: G-WITNESS coverage advisory: the fraction of in-scope expansions the boost
#: actually reached. ⛔ ADVISORY — it FLAGS, it does not void. A hard equality
#: here would be the PG-A1 shape (a gate no healthy archive can pass).
WITNESS_COVERAGE_FLOOR = 0.5

RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"


# =========================================================================== #
# 1. THE CELLS                                                                 #
# =========================================================================== #

@dataclass(frozen=True)
class CellSpec:
    """One archive = one ARM. ⭐ All three arms share ONE deck set (CRN)."""

    name: str
    role: str                       #: "local" | "laptop" — `G-HOST`'s frozen box
    scope: str                      #: "opp" | "own" | "all" — THE single variable
    seed_start: int
    n_decks: int
    purpose: str

    @property
    def n_games(self) -> int:
        return self.n_decks * 2

    @property
    def seed_end(self) -> int:
        """INCLUSIVE last seed of this arm's deck range."""
        return self.seed_start + self.n_decks - 1

    @property
    def dose(self) -> float:
        return JR_DOSE

    @property
    def mask(self) -> int:
        return JR_MASK

    @property
    def cand_jrules_prior(self) -> dict:
        """The RESOLVED candidate-side block `eval_fair_puct` must emit at
        `manifest.config.cand_jrules_prior`."""
        return {"dose": JR_DOSE, "mask": JR_MASK, "scope": self.scope}


#: ⭐⭐ THE THREE ARMS, owner-ratified 2026-08-30. ONE shared deck set, deck-paired
#: and seat-balanced, every arm against the UNMODIFIED champion.
#: ⭐ BOX ASSIGNMENT IS WHOLE ARMS PER BOX (`G-HOST`) — disjoint `--out-subdir`
#: per arm means there are no shared claims to race over, which is the real
#: protection (the FPU precedent). local:laptop capacity is ~1.49:1 (W 30 vs
#: 22/1.0935), so OPP+ALL local / OWN laptop is the balanced whole-arm split of
#: 3,200 games.
#: ⚠️ DISCLOSED, NOT ENGINEERED AWAY: P2's two arms therefore run on DIFFERENT
#: BOXES, so a mixed-rev or mixed-wheel defect would land ASYMMETRICALLY on the
#: primary contrast. That is exactly what the round-level `G-REV` and `G-TOOL`
#: gates exist for, and games are bit-identical at any W. The co-located variant
#: (`--role local` for all three arms, +~2 h wall) changes NO bar, NO band and NO
#: seed and is available to the orchestrator pre-launch.
CELLS: tuple[CellSpec, ...] = (
    CellSpec("CELL_G3_OPP", "local", "opp", BAND, 600,
             "⭐⭐ THE PRIMARY CANDIDATE — the anchor's J bundle as priors at "
             "OPPONENT-mover expansions only. Under `opp` the ROOT expansion is "
             "byte-identical to the champion's BY DESIGN, so every behavioural "
             "difference is SEARCH-MEDIATED. n=1,200 per SIZING §4.1(b): at "
             "n=800 the design's own predicted +1 pt/deck reads z≈1.6, i.e. "
             "`S1-BOUNDED-NULL` would be the modal outcome even if the effect "
             "is real."),
    CellSpec("CELL_G3_OWN", "laptop", "own", BAND, 600,
             "⭐ THE DECOMPOSITION CONTROL — the same bundle at the ROOT "
             "PLAYER's own expansions, i.e. the complement of `opp`. It is NOT "
             "optional (DESIGN §4.2): without it a null on `opp` alone cannot "
             "distinguish 'no asymmetry effect' from 'both components ≈ 0'. It "
             "is also §5.4's ruler probe — if its G-DENY rises, the control arm "
             "has produced the exploit-expressing opponent CL-083 needs."),
    CellSpec("CELL_G3_ALL", "local", "all", BAND, 400,
             "⭐ THE IN-BAND SYMMETRIC CONTROL — the 'is this just another "
             "dose?' arm the design owes. The banked surface-B `all` null sits "
             "on a RETIRED band at the SUPERSEDED 11008 budget, and CL-068 "
             "forbids differencing it (DESIGN §4.3), so `all` is re-measured "
             "IN-BAND at 22016. n=800: the control only needs to reproduce a "
             "known null, and 2σ = ±1.26 does that."),
)


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"unknown cell {name!r}; known: {[c.name for c in CELLS]}")


def cells_of_box(role: str) -> tuple[CellSpec, ...]:
    return tuple(c for c in CELLS if c.role == role)


#: The shared deck set every arm draws from. ALL plays a PREFIX SUBSET of it.
SHARED_DECKS = (BAND, BAND + max(c.n_decks for c in CELLS) - 1)


# =========================================================================== #
# 2. ADDRESS RESOLUTION — IS-D1 (carried verbatim from the FPU/phasegate pair)  #
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

    ⛔ EVERY gate prints the address that answered. IS-D1's original defect was a
    precheck that read `config` off `summary.json` — which carries NO config
    block at all — got `{}`, failed closed on one conjunct and passed VACUOUSLY
    on another. **Config comes from `manifest.json`, statistics from
    `summary.json`, and no knob is ever quoted from a directory name.**

    ⚠️⚠️ `MISSING` IS NOT `None`. `cand_jrules_prior: null` is a POSITIVE
    statement ("surface B is OFF on this side") while an ABSENT key means the
    harness never resolved it. No gate may collapse the two.
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
# 3. REV / PROVENANCE                                                          #
# =========================================================================== #

def split_dirty(code_rev) -> tuple[str, bool]:
    s = str(code_rev or "")
    if s.endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def is_hex40(s) -> bool:
    s = str(s or "")
    return len(s) == 40 and all(c in "0123456789abcdef" for c in s)


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """A manifest's `code_rev` may be an ABBREVIATED sha; the pin is 40-hex.

    ⛔ `-dirty` is ALWAYS a fail: a dirty tree is a tree whose source is not the
    pin, whatever the prefix says."""
    base, dirty = split_dirty(code_rev)
    if dirty:
        return False, f"code_rev {code_rev!r} is DIRTY — the source is not the pin"
    if not base:
        return False, "code_rev ABSENT — ABSENT is FAIL"
    if not is_hex40(pinned):
        return False, f"the pin {pinned!r} is not a 40-hex sha"
    if len(base) < MIN_REV_PREFIX:
        return False, (f"code_rev {base!r} is shorter than {MIN_REV_PREFIX} hex "
                       "— too short to witness anything")
    if not pinned.startswith(base):
        return False, f"code_rev {base!r} is not a prefix of the pin {pinned!r}"
    return True, f"code_rev {base!r} is a prefix of the pinned {pinned!r}"


def cross_box_rev_gate(revs_by_cell: Mapping, pins_by_role: Mapping) -> dict:
    """`G-REV` — every arm ran the SAME source rev, and that rev is the pin its
    box recorded.

    ⚠️⚠️ THIS ROUND'S PRIMARY PROVENANCE RISK, and it has a NEW shape relative to
    FPU's. `--cand-jrules-prior-scope opp` needs a POST-S1 `carc_rs` wheel: a
    stale wheel raises at config construction (fail-closed `ValueError`) rather
    than running knob-free, which is the good case. The BAD case is a box whose
    PYTHON source predates the R7 witness: it would run the scope correctly and
    emit NO `jr_expansions`, and `G-WITNESS` would then VOID a healthy cell. Both
    failure modes are caught here before a statistic is read.
    ⭐ P2's two arms run on DIFFERENT BOXES, so this gate is load-bearing for the
    primary contrast, not hygiene."""
    seen, bad = {}, []
    for name, (rev, role) in sorted(revs_by_cell.items()):
        base, dirty = split_dirty(rev)
        seen[name] = {"code_rev": rev, "role": role, "dirty": dirty}
        pin = pins_by_role.get(role)
        if pin is None:
            bad.append(f"{name}: no PINNED_SRC_REV for role {role!r} — "
                       "ABSENT is FAIL")
            continue
        ok, why = rev_matches(rev, pin)
        seen[name]["pin"] = pin
        seen[name]["why"] = why
        if not ok:
            bad.append(f"{name}: {why}")
    bases = {split_dirty(v["code_rev"])[0] for v in seen.values()
             if v["code_rev"]}
    if len(bases) > 1:
        # Abbreviated shas of the SAME commit differ in LENGTH, not content.
        srt = sorted(bases, key=len)
        if not all(b.startswith(srt[0]) for b in srt):
            bad.append(f"⛔ MIXED-REV ROUND: the arms carry {sorted(bases)} — "
                       "a decomposition whose arms ran different source is not "
                       "a decomposition.")
    return gate("G-REV", not bad, seen, "manifest:code_rev vs PINNED_SRC_REV",
                ("every arm ran one source rev and it is the pin its box "
                 "recorded" if not bad else "⛔ G-REV FAILED: " + "; ".join(bad)))


_HOST_ALIASES = {"laptop": ("laptop", "laptop-wsl", "laptop-pop", "pop-os", "pop"),
                 "local": ("doctor", "5800x", "desktop", "localhost")}


def host_matches_box(observed_host, role: str) -> tuple[bool, str]:
    h = str(observed_host or "").strip().lower()
    if not h:
        return False, "host ABSENT — ABSENT is FAIL"
    lap = any(a in h for a in _HOST_ALIASES["laptop"])
    if role == "laptop":
        return lap, (f"host {h!r} is the laptop" if lap else
                     f"host {h!r} is NOT the laptop")
    return (not lap), (f"host {h!r} is not the laptop, so it is the local box"
                       if not lap else f"host {h!r} is the LAPTOP, not local")


# =========================================================================== #
# 4. THE STATISTICS — recomputed from raw records, never trusted from summary  #
# =========================================================================== #

def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}`. A record missing `seed`, `a_seat` or `diff` is
    DROPPED here and shows up as a short `n_paired` at `G-PAIRED` — it is never
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
    in BOTH seatings. A deck missing a seating is DROPPED, never zero-filled.
    `diff` is CANDIDATE minus OPPONENT in POINTS, so `D > 0` ⇒ the candidate won."""
    return {s: (v[0] + v[1]) / 2.0
            for s, v in sorted(_by_deck(records).items()) if 0 in v and 1 in v}


def paired_margin(records: Iterable[Mapping]):
    """P1's statistic, recomputed from the raw records.

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


def paired_contrast(a_records, b_records) -> dict:
    """⭐⭐ **P2 — THE ASYMMETRY CONTRAST**, `D = margin(OPP) − margin(OWN)`, on
    the **SHARED** deck set. The `tiearb_widening` `WIDE − NARROW` precedent,
    which used exactly this statistic as its primary.

    ⛔ IT IS A **PER-DECK** DIFFERENCE, not a difference of two means. Differencing
    the means throws away the CRN that the shared deck set was bought for, and
    would price P2 at ρ=0 no matter what the true correlation is. The realized ρ
    is reported so the gain is visible.

    A deck present in only ONE arm is DROPPED — it carries no contrast."""
    A, B = per_deck_margins(a_records), per_deck_margins(b_records)
    common = sorted(set(A) & set(B))
    n = len(common)
    if n < 2:
        return {"D": None, "z": None, "se": None, "n_common": n,
                "rho_realized": None, "per_deck": [],
                "why": "fewer than 2 shared decks — no contrast exists"}
    diffs = [A[s] - B[s] for s in common]
    mean = math.fsum(diffs) / n
    var = math.fsum((d - mean) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var / n)
    a_vals = [A[s] for s in common]
    b_vals = [B[s] for s in common]
    ma, mb = math.fsum(a_vals) / n, math.fsum(b_vals) / n
    va = math.fsum((x - ma) ** 2 for x in a_vals) / (n - 1)
    vb = math.fsum((x - mb) ** 2 for x in b_vals) / (n - 1)
    cov = math.fsum((x - ma) * (y - mb) for x, y in zip(a_vals, b_vals)) / (n - 1)
    rho = (cov / math.sqrt(va * vb)) if va > 0 and vb > 0 else None
    return {"D": mean, "z": (mean / se) if se > 0 else float("nan"), "se": se,
            "n_common": n, "rho_realized": rho, "per_deck": diffs,
            "why": "per-deck OPP−OWN on the shared deck set (CRN preserved)"}


PAIRING_FACTOR = 1.0 / math.sqrt(2.0)


def elo_sigma_unpaired(wr: float, n_games: int) -> float:
    """1σ on elo from the plain binomial, treating every GAME as independent.
    ⛔ THE WRONG FOOTING for this cell; emitted only so the correction is
    auditable."""
    return ((400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n_games)
            / (wr * (1 - wr)))


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from the raw records.

    ⚠️⚠️ THE EMITTED SIGMA IS DECK-PAIRED and says so IN THE FIELD NAME. A
    footing that is not in the field name is a footing nobody checks.
    ⛔ ELO IS A COMPANION HERE, NEVER A BRANCH INPUT — the deck-paired MARGIN
    carries every branch (`feedback_trend_beats_underpowered_steps`)."""
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
    """`SIGMA_D_MODEL / sqrt(n)`. 600 decks -> 0.5144; 400 -> 0.6300.
    ⛔ POWER ARITHMETIC ONLY — never a denominator in a branch test."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_model_contrast(n_common: int, rho: float = RHO_FROZEN) -> float:
    """`sem_D = SEM_800 * sqrt(2(1-rho)) * sqrt(800/n_games)` (SIZING §4).
    ⛔ POWER ARITHMETIC ONLY."""
    return se_model(n_common) * math.sqrt(2.0 * (1.0 - rho))


def sigma_elo(n_games: int) -> float:
    """Realized 1σ elo scaled from `SIGMA_ELO_800`. ⛔ POWER ARITHMETIC ONLY."""
    return SIGMA_ELO_800 * math.sqrt(800.0 / float(n_games))


def se_anomaly(realized_se, n_decks: int) -> dict:
    """Print realized vs modelled SE and FLAG a ratio outside `SE_ANOMALY_BAND`.
    ⛔ Reported, NEVER a branch input."""
    modelled = se_model(n_decks) if n_decks else 0.0
    if realized_se is None or modelled <= 0:
        return {"realized": realized_se, "modelled": modelled or None,
                "ratio": None, "band": list(SE_ANOMALY_BAND), "flagged": True,
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


def power_at(delta: float, se: float, z_bar: float = HOLM_Z[0]) -> float:
    """Two-sided power to clear `z_bar` at true effect `delta`."""
    if se is None or se <= 0:
        return float("nan")
    lam = delta / se
    return (1.0 - _phi(z_bar - lam)) + _phi(-z_bar - lam)


# =========================================================================== #
# 5. THE BRANCH MAP — DESIGN §6.4, frozen                                      #
# =========================================================================== #

BRANCHES = ("S1-VOID-INSTRUMENT", "S1-FIRES", "S1-MARGIN-ONLY",
            "S1-ASYMMETRY-ONLY", "S1-ASYMMETRY-REVERSED", "S1-NEGATIVE",
            "S1-BOUNDED-NULL")


def holm(z_p1, z_p2) -> dict:
    """⭐⭐ THE DUAL PRIMARY'S HOLM LADDER (step-down, two-sided, family α=0.05).

    The LARGER |z| is tested at `HOLM_Z[0]`; only if it clears is the smaller
    tested at `HOLM_Z[1]`. A leg that does not clear does not fire a branch.
    ⛔ There is no third test. G2's signature, the ALL arm, the elo and every
    companion are OUTSIDE the family by construction, which is what keeps the
    family size at 2."""
    legs = []
    for name, z in (("P1", z_p1), ("P2", z_p2)):
        legs.append({"leg": name, "z": z,
                     "abs_z": (abs(z) if z is not None and not
                               (isinstance(z, float) and math.isnan(z))
                               else None)})
    order = sorted(legs, key=lambda l: (-1.0 if l["abs_z"] is None
                                        else -l["abs_z"]))
    stopped = False
    for i, leg in enumerate(order):
        thr = HOLM_Z[i]
        leg["holm_step"] = i + 1
        leg["holm_threshold"] = thr
        # ⛔ ALWAYS set, even on a stopped leg: the nominal 2σ verdict is what
        # makes a marginal case VISIBLE, and a key that only exists when the
        # ladder ran is a key the readout cannot rely on.
        leg["clears_nominal_2sigma"] = (leg["abs_z"] is not None
                                        and leg["abs_z"] >= NOMINAL_Z)
        if stopped or leg["abs_z"] is None:
            leg["clears"] = False
            leg["why"] = ("the ladder STOPPED at an earlier step (Holm is "
                          "step-down)" if stopped else
                          "|z| unavailable — ABSENT is FAIL")
            stopped = True
            continue
        leg["clears"] = leg["abs_z"] >= thr
        leg["why"] = (f"|z| {leg['abs_z']:.4f} "
                      f"{'>=' if leg['clears'] else '<'} {thr} "
                      f"(Holm step {i + 1})")
        if not leg["clears"]:
            stopped = True
    by = {l["leg"]: l for l in legs}
    return {"legs": legs, "P1_clears": by["P1"]["clears"],
            "P2_clears": by["P2"]["clears"],
            "family": "{P1 deployability, P2 asymmetry}", "alpha": 0.05,
            "thresholds": list(HOLM_Z),
            "note": "⛔ the branch reads the HOLM ladder; DESIGN §6.4's '≥ +2σ' "
                    "shorthand is the correction DESIGN itself names, and 2.0 "
                    "sits inside the bracket [1.96, 2.2414]. The nominal 2σ "
                    "verdict is reported per leg but is NOT the rule."}


def branch_for_round(*, gates_ok: bool, z_p1, z_p2,
                     signature_bar_met) -> tuple[str, dict]:
    """⭐ THE ONE PLACE A BRANCH IS DECIDED. `signature_bar_met` is G2's verdict
    and is `None` when the census is UNAVAILABLE — which can never read as met.

    ⛔ `|z| < 2` IS NEVER "REFUTED" (DESIGN §10.3). *Killed / dead / does
    nothing* are forbidden readings of a bounded null; the bound is quoted."""
    h = holm(z_p1, z_p2)
    if not gates_ok:
        return "S1-VOID-INSTRUMENT", h
    if h["P1_clears"]:
        if z_p1 > 0:
            return (("S1-FIRES" if signature_bar_met is True
                     else "S1-MARGIN-ONLY"), h)
        return "S1-NEGATIVE", h
    if h["P2_clears"]:
        return (("S1-ASYMMETRY-ONLY" if z_p2 > 0
                 else "S1-ASYMMETRY-REVERSED"), h)
    return "S1-BOUNDED-NULL", h


#: What each branch LICENSES. ⛔ None of them licenses a `PRODUCTION.yaml`
#: change: a screen aims, it does not verdict (DESIGN §10.6).
BRANCH_CONSEQUENCE = {
    "S1-VOID-INSTRUMENT":
        "⛔ THE READ IS VOID. Fix the instrument, re-run, read again. A void is "
        "NOT a null and may never be quoted as one (IS-A1 precedent). ⚠️ The "
        "voided artefacts stay on disk UNMODIFIED; the amended re-read is a new "
        "document.",
    "S1-FIRES":
        "P1 cleared POSITIVE and G2's signature bar was met. Licences a CONFIRM "
        "at n >= 1,600 on a FRESH band plus the G4 guards (Carcasum @5000 ms, "
        "n=400 — CL-083's own non-regression clause). ⛔ NO ADOPTION ON A "
        "SCREEN. ⚠️ Arbiter-off ⇒ deploy transfer is an ASSUMPTION and must be "
        "stated in the readout, not buried (DESIGN §10.5).",
    "S1-MARGIN-ONLY":
        "P1 cleared POSITIVE but the G2 signature bar was NOT met — or the "
        "census was UNAVAILABLE. Per DESIGN §10.4: this licenses THE NUMBER, "
        "not the MECHANISM STORY. Report it that way. A confirm may be proposed "
        "only with the census in hand, because a margin win with a flat "
        "signature means the mechanism is not the stated one.",
    "S1-ASYMMETRY-ONLY":
        "P2 cleared POSITIVE, P1 did not: the DECOMPOSITION is real, the "
        "DEPLOYABLE half is not. Report; fund option (i-b) or a top-up. ⛔ DO "
        "NOT ADOPT — `opp − own` being positive is compatible with `opp` itself "
        "being worthless (it only says `own` is worse).",
    "S1-ASYMMETRY-REVERSED":
        "P2 cleared NEGATIVE: `own` beat `opp` on the shared decks. This is the "
        "decomposition running the OTHER WAY and it is evidence AGAINST the "
        "mechanism argument (DESIGN §4: 'the separation rests entirely on the "
        "own-component being negative'). Record it as such. Derived at freeze "
        "from DESIGN §4, pre-outcome — DESIGN §6.4's table has no row for it, "
        "and a branch map with a hole is worse than one with a named floor.",
    "S1-NEGATIVE":
        "P1 cleared NEGATIVE: opponent-node modelling is HARMFUL at this dose. "
        "Closes with the CL-080/CL-082 family. ⚠️ If `N4-COST` also fired, the "
        "loss is CONFOUNDED BY BUDGET and must be reported as surface A's was "
        "(realized ms_ratio 1.2116), not as a clean harm result.",
    "S1-BOUNDED-NULL":
        "Neither leg cleared. RECORD THE BOUND and close the branch: re-opening "
        "needs a MECHANISM argument, not more n. ⛔ `|z| < 2` is never "
        "'refuted' (DESIGN §10.3) — quote the bound, in pts/deck, on the "
        "realized SE.",
}


#: Riders that print on EVERY branch. ⛔ NEVER BRANCH INPUTS.
RIDERS_ALWAYS = (
    "⛔ A FLIP IS NOT AN IMPROVEMENT and d* is not 'the right dose'. G1 measured "
    "EXPRESSION at 5.01% and expression is not effect (READ_RULE_G1 §6.1/§6.5); "
    "the CL-080 anchor is 10.09% flip -> −53.8 elo.",
    "⛔ NO CONTRAST WITH THE BANKED SURFACE-B `all` CELL IS A STATISTIC. "
    "Different band (1.30e11, retired), different budget (11008), and CL-068 "
    "prices cross-band contrasts at 1.8–2.2x over-dispersion. The IN-BAND ALL "
    "arm is the only differenceable control (DESIGN §10.2).",
    "⚠️ ARBITER-OFF BOTH SIDES is a deliberate deviation from the deployed "
    "champion (tiearb B=64). DEPLOY TRANSFER IS AN ASSUMPTION and rides on "
    "every branch (DESIGN §10.5).",
    "⛔ NOTHING HERE LICENSES A `PRODUCTION.yaml` CHANGE. A screen aims; it does "
    "not verdict (DESIGN §10.6).",
    "⛔ THE THREE ARMS' `jr_expansions` CENSUSES ARE NOT ADDITIVE ACROSS ARMS. "
    "`own` and `opp` boost disjoint sets whose union is `all`'s WITHIN ONE "
    "TREE (DESIGN §9.2c) — three separate searches do not build the same trees, "
    "so `OWN.boosted + OPP.boosted ≈ ALL.boosted` is NOT a check and must not "
    "be reported as one.",
    "⛔ THE ALL ARM IS A CONTROL, NOT A THIRD PRIMARY. It is outside the Holm "
    "family by construction; no branch reads it and no bar is stated on it. It "
    "answers exactly one question: 'is this just another dose?'",
)


# =========================================================================== #
# 6. THE GATES                                                                 #
# =========================================================================== #

#: Search-config aliases BOTH sides emit and that must be IDENTICAL. ⛔ The
#: candidate's `cand_jrules_prior` block is the ONE permitted difference.
#: ⚠️ VERIFIED AGAINST THE EMITTER, not against the design (the PG-A1 lesson):
#: the candidate's block is `HeuristicPriorConfig.as_manifest()` plus the budget
#: (`eval_fair_puct.py:4586-4592`); the opponent's `champ_cfg` is the five-key
#: `champ_cfg_dict` (`eval_fair_puct.py:2950-2961`) and its budget lives one
#: level up at `config.opponent.*`, which `_sides` resolves as a fallback.
SINGLEVAR_ALIASES = ("k_dets", "sims_per_det", "total_sims", "c_puct", "tau_p",
                     "leaf_quantize", "final_select", "value_norm")

#: ⚠️⚠️ ASYMMETRICALLY EMITTED, AND THAT IS HEALTHY — so a bare
#: present-on-one-side-only rule would void every healthy cell (PG-A1's exact
#: shape). `fpu_reduction` is stated POSITIVELY in the opponent's `champ_cfg`
#: (the FPU round added it there so `G-FPU` could assert the opponent side) but
#: `as_manifest()` does NOT emit it for the candidate. An ABSENT side is
#: therefore read as its documented DEFAULT, and both sides must equal it.
SINGLEVAR_ONESIDED_DEFAULTS = {
    "fpu_reduction": (None, "the champion's legacy optimistic q=0"),
}


def singlevar_gate(spec: CellSpec, rows: Mapping[str, Mapping]) -> dict:
    """`G-SINGLEVAR` — the candidate differs from the opponent in the SCOPE KNOB
    AND NOTHING ELSE.

    ⚠️ The opponent's search knobs live ONE LEVEL DOWN under
    `config.opponent.champ_cfg.*`; a gate written from the design rather than
    from a real manifest voids every healthy cell (the phasegate `G-SINGLEVAR`
    lesson, carried).

    ⚠️ An alias ABSENT ON BOTH sides is NOT a violation — the harness simply does
    not emit it. An alias present on ONE side only IS, *unless* it is a known
    asymmetric emission (`SINGLEVAR_ONESIDED_DEFAULTS`), in which case the absent
    side reads as its documented default and the comparison still happens."""
    bad, seen = [], {}
    # ⛔ ABSENT IS FAIL, and "absent on both sides" must not become a VACUOUS
    # PASS on an archive that has no manifest at all — the IS-D1 class of defect.
    # A healthy cell always resolves the budget and the four search knobs.
    if all(r["champion_absent"] and r["opponent_absent"] for r in rows.values()):
        return gate("G-SINGLEVAR", False, dict(rows),
                    "manifest:config.champion.* vs "
                    "manifest:config.opponent.champ_cfg.*",
                    "⛔ G-SINGLEVAR FAILED: NOT ONE search alias resolved on "
                    "either side. There is nothing to compare, so this is "
                    "ABSENT, not agreement (IS-D1: a gate that passes because "
                    "it read `{}` proves nothing).")
    for alias, row in rows.items():
        seen[alias] = dict(row)
        ca, oa = row["champion_absent"], row["opponent_absent"]
        if ca and oa:
            continue
        if ca != oa:
            if alias in SINGLEVAR_ONESIDED_DEFAULTS:
                dflt, why = SINGLEVAR_ONESIDED_DEFAULTS[alias]
                cv = dflt if ca else row["champion"]
                ov = dflt if oa else row["opponent"]
                seen[alias]["default_applied"] = {"value": dflt, "why": why}
                if cv != ov or cv != dflt:
                    bad.append(f"{alias}: candidate {cv!r} / opponent {ov!r}, "
                               f"and the documented default is {dflt!r} ({why})")
                continue
            bad.append(f"{alias}: present on ONE side only "
                       f"(candidate_absent={ca}, opponent_absent={oa})")
            continue
        if row["champion"] != row["opponent"]:
            bad.append(f"{alias}: candidate {row['champion']!r} != opponent "
                       f"{row['opponent']!r}")
    return gate("G-SINGLEVAR", not bad, seen,
                "manifest:config.champion.* vs manifest:config.opponent.champ_cfg.*",
                ("the two sides agree on every shared search alias; the ONLY "
                 "difference is the candidate's cand_jrules_prior block"
                 if not bad else "⛔ G-SINGLEVAR FAILED: " + "; ".join(bad)))


def scope_gate(spec: CellSpec, resolved, addr,
               opp_resolved, opp_addr) -> dict:
    """`G-SCOPE` — the RESOLVED candidate block is `{dose, mask, scope}` at this
    arm's frozen values, and the OPPONENT carries no jrules prior at all.

    ⛔ THE WIRING GATE FOR THIS SURFACE IS THIS RESOLVED DICT. Surface B moves NO
    leaf hash (`eval_fair_puct.py:4773-4777`), so `cand_leaf_hash` EQUALS the
    champion's on a live cell and a moved-hash check proves NOTHING here.
    ⚠️ CONFIG-LEVEL ONLY. It proves the knob was REQUESTED and RESOLVED; it does
    NOT prove the knob BOUND IN PLAY. `G-WITNESS` is the half that does, and it
    is why this round exists (the FPU round is the standing lesson that a knob
    can silently never bind)."""
    want = spec.cand_jrules_prior
    bad = []
    if resolved is MISSING:
        bad.append("config.cand_jrules_prior ABSENT — ABSENT is FAIL")
    elif resolved is None:
        bad.append("config.cand_jrules_prior is null == surface B is OFF on the "
                   "CANDIDATE — this arm would be champion-vs-champion")
    elif not isinstance(resolved, Mapping):
        bad.append(f"config.cand_jrules_prior is {type(resolved).__name__}, "
                   "not a resolved dict")
    else:
        for k, v in want.items():
            got = resolved.get(k, MISSING)
            if got is MISSING:
                bad.append(f"cand_jrules_prior.{k} ABSENT")
            elif isinstance(v, float):
                if not recon_close(got, v):
                    bad.append(f"cand_jrules_prior.{k} = {got!r}, frozen {v!r}")
            elif got != v:
                bad.append(f"cand_jrules_prior.{k} = {got!r}, frozen {v!r}")
    # the opponent must carry NO jrules prior. ABSENT is the EXPECTED shape here
    # (champ_cfg_dict states only five keys; _cfg_from_dict reads them by name
    # and ignores the rest), so ABSENT is OK and PRESENT-AND-LIVE is the defect.
    if opp_resolved is not MISSING and opp_resolved:
        try:
            d = float((opp_resolved or {}).get("dose", 0.0))
        except (TypeError, ValueError, AttributeError):
            d = float("nan")
        if not (d == 0.0):
            bad.append(f"the OPPONENT carries a live jrules prior "
                       f"{opp_resolved!r} at {opp_addr} — a scoped arm whose "
                       "opponent is also armed is not a decomposition")
    return gate("G-SCOPE", not bad,
                {"resolved": None if resolved is MISSING else resolved,
                 "frozen": want,
                 "opponent_jrules_prior": (None if opp_resolved is MISSING
                                           else opp_resolved),
                 "addresses": [addr, opp_addr]},
                addr,
                (f"the candidate resolved dose {want['dose']} mask "
                 f"{want['mask']} scope {want['scope']!r} and the opponent "
                 "carries no jrules prior" if not bad else
                 "⛔ G-SCOPE FAILED: " + "; ".join(bad)))


#: ⭐⭐ `G-WITNESS`'s ACCEPTED ADDRESSES, first-that-answers, address printed.
#: ⭐ **THE R7 WITNESS BUILD'S FINAL EMITTED CONTRACT** (sibling agent, 2026-08-30
#: — it SUPERSEDES the shape this gate was first drafted against). The block is
#: written at TWO addresses in `summary.json` and BOTH are tried, because a cell
#: must not void on a key spelling (the `cand_tiearb.fires` precedent):
#:     summary["jr_expansions"]["candidate"|"opponent"]
#:     summary["cand_jr_expansions"] / summary["opp_jr_expansions"]
#: each == `{"total": N, "own_mover": N, "boosted": N}`, mirroring
#: `carc_core::search::SearchResult::jr_expansions_{total,own_mover,boosted}`
#: (`rust/carc/carc-core/src/search/mod.rs:493-508`). Per-game records carry
#: `cand_jr_expansions` / `opp_jr_expansions` at the same shape.
#: ⛔ NONE ANSWERING IS A **VOID**, NEVER A SKIP.
WITNESS_ADDRESSES = {
    "candidate": ("summary:jr_expansions.candidate",
                  "summary:cand_jr_expansions",
                  "summary:jr_expansions.cand"),
    "opponent": ("summary:jr_expansions.opponent",
                 "summary:opp_jr_expansions",
                 "summary:jr_expansions.opp"),
}

WITNESS_KEYS = ("total", "own_mover", "boosted")


def _scope_denominator(scope: str, total: int, own_mover: int) -> tuple[int, str]:
    """How many expansions THIS scope is entitled to boost."""
    if scope == "own":
        return own_mover, "own_mover"
    if scope == "opp":
        return total - own_mover, "total - own_mover"
    return total, "total"


def witness_gate(spec: CellSpec, cand, cand_addr, opp, opp_addr) -> dict:
    """⭐⭐ `G-WITNESS` — **THE PLAY-DERIVED PROOF THAT THE SCOPE KNOB BOUND.**

    ⛔⛔ THIS GATE IS WHY THE ROUND HAS A PRE-LAUNCH CONDITION. G1's verdict
    recorded that played `scope='opp'` cells carried **only a config echo**: the
    rust counters exist (`search/mod.rs:699-704`) but `fair::search_worlds`
    discarded them at `fair/mod.rs:810-814` (`.map(|r| r.pooled_stats)`). A cell
    whose knob never bound is champion-vs-champion wearing a candidate's name: it
    moves no leaf hash, sits inside every rail, and reads as a clean credible
    null. The FPU-RESURRECTION round exists because exactly that happened.

    ⛔ **ABSENT IS VOID, NOT PASS.** A missing key means the R7 witness build is
    not on this box, and a round read without it proves nothing.

    ⚠️⚠️ **THE UNARMED SIDE READS ALL ZEROS, AND THAT IS THE HEALTHY SHAPE.**
    The R7 build's per-tree counters live INSIDE the `dose != 0` branch, so the
    opponent — which is the unmodified champion and carries no jrules prior —
    emits `{total: 0, own_mover: 0, boosted: 0}`, **not** `{T, M, 0}` with
    `T > 0`. ⛔ Asserting `opponent.total > 0` would therefore fail EVERY healthy
    cell: that is the PG-A1 shape (a gate written to the reader's expectation
    rather than to the emitter's real output) and it is excluded by construction
    here. The opponent's ONLY hard assertion is `boosted == 0`.

    HARD checks (any failure ⇒ the arm VOIDS):
      1. both sides resolve to a mapping carrying all three integer keys;
      2. **candidate** `total > 0` — the armed side's census ran at all;
      3. `0 <= own_mover <= total` on both sides — the census is coherent;
      4. **candidate `boosted > 0`** — the knob EXPRESSED IN PLAY;
      5. **opponent `boosted == 0`** — it is CANDIDATE-SIDE ONLY;
      6. candidate `boosted <= ` this scope's own denominator — the boost never
         reached a node OUTSIDE its scope. This is the machine-checkable half of
         DESIGN §9.2(c) ("Own and Opp boost disjoint sets whose union is All's").

    ADVISORY (flags, never voids): `coverage = boosted / denominator`. A hard
    equality here would be the PG-A1 shape — a gate no healthy archive can pass —
    because terminal and no-legal-child expansions legitimately boost nothing.
    """
    bad, notes = [], []
    rows = {}

    def _norm(v, side, addr):
        if v is MISSING:
            bad.append(f"{side}: NO address answered for jr_expansions "
                       f"(tried {list(WITNESS_ADDRESSES[side])}) — ⛔ ABSENT is "
                       "VOID, not pass. The R7 witness build is not on this box.")
            return None
        if not isinstance(v, Mapping):
            bad.append(f"{side}: jr_expansions at {addr} is "
                       f"{type(v).__name__}, not a mapping")
            return None
        out = {}
        for k in WITNESS_KEYS:
            if k not in v:
                bad.append(f"{side}: jr_expansions.{k} ABSENT at {addr}")
                return None
            try:
                out[k] = int(v[k])
            except (TypeError, ValueError):
                bad.append(f"{side}: jr_expansions.{k} = {v[k]!r} is not an int")
                return None
        return out

    c = _norm(cand, "candidate", cand_addr)
    o = _norm(opp, "opponent", opp_addr)
    rows["candidate"] = c
    rows["opponent"] = o
    rows["addresses"] = {"candidate": cand_addr, "opponent": opp_addr}

    coverage = None
    for side, r, addr in (("candidate", c, cand_addr), ("opponent", o, opp_addr)):
        if r is None:
            continue
        # ⛔ ARMED-SIDE ONLY. The unarmed opponent legitimately reads all zeros
        # (the counters live inside the `dose != 0` branch), so a `total > 0`
        # assertion on that side would fail every healthy cell.
        if side == "candidate" and r["total"] <= 0:
            bad.append(f"{side}: total = {r['total']} — the ARMED side's "
                       "expansion census never ran. Either the dose did not "
                       "reach the search or the R7 counters are not wired on "
                       "this box's build.")
        if not (0 <= r["own_mover"] <= max(r["total"], 0)):
            bad.append(f"{side}: own_mover {r['own_mover']} outside [0, total="
                       f"{r['total']}] — the census is incoherent")
        if r["boosted"] < 0:
            bad.append(f"{side}: boosted {r['boosted']} < 0")

    if c is not None and c["total"] > 0:
        if c["boosted"] <= 0:
            bad.append("⛔⛔ candidate boosted == 0: THE SCOPE KNOB NEVER BOUND "
                       "IN PLAY. This arm is champion-vs-champion wearing a "
                       "candidate's name — the exact defect the FPU round "
                       "exists for.")
        den, den_expr = _scope_denominator(spec.scope, c["total"], c["own_mover"])
        rows["scope_denominator"] = {"scope": spec.scope, "expr": den_expr,
                                     "value": den}
        if den < 0:
            bad.append(f"candidate: the {spec.scope!r} denominator ({den_expr}) "
                       f"is {den} — own_mover exceeds total")
        elif c["boosted"] > den:
            bad.append(f"⛔ candidate boosted {c['boosted']} EXCEEDS the "
                       f"{spec.scope!r} scope's own node count ({den_expr} = "
                       f"{den}) — the boost reached OUTSIDE its scope, which "
                       "breaks the own/opp disjointness DESIGN §9.2(c) asserts.")
        elif den > 0:
            coverage = c["boosted"] / float(den)
            if coverage < WITNESS_COVERAGE_FLOOR:
                notes.append(
                    f"⚠️ ADVISORY: coverage {coverage:.4f} = boosted/{den_expr} "
                    f"is below the {WITNESS_COVERAGE_FLOOR} advisory floor. "
                    "FLAGGED, NEVER VOIDING — terminal and no-legal-child "
                    "expansions legitimately boost nothing, and a hard bar here "
                    "would be the PG-A1 shape (a gate no healthy archive can "
                    "pass). Read it as 'the surface is thinner than expected', "
                    "not as a defect.")

    if o is not None and o["boosted"] != 0:
        bad.append(f"⛔⛔ opponent boosted = {o['boosted']} != 0: THE KNOB BOUND "
                   "ON BOTH SIDES. A scoped arm whose opponent is also armed "
                   "measures nothing — this is the `--c-puct` both-sides trap "
                   "in its jrules disguise.")

    rows["coverage"] = coverage
    rows["advisories"] = notes
    return gate("G-WITNESS", not bad, rows, cand_addr,
                ("⭐ the scope knob BOUND IN PLAY on the candidate "
                 f"(boosted > 0, inside the {spec.scope!r} scope) and did NOT "
                 "bind on the opponent (boosted == 0; the unarmed side reads "
                 "all zeros, which is the healthy shape)" if not bad else
                 "⛔ G-WITNESS FAILED: " + " | ".join(bad)))


def leaf_gate(cand_hash, opp_hash) -> dict:
    """`G-LEAF`, **INVERTED**: the candidate's leaf hash must **EQUAL** the
    champion's. Surface B changes priors, never the leaf — a MOVED hash means a
    leaf change was smuggled into a prior cell (READ_RULE_G1 §5.2)."""
    bad = []
    for label, h in (("cand_leaf_hash", cand_hash), ("opp_leaf_hash", opp_hash)):
        if h is None:
            bad.append(f"{label} ABSENT — ABSENT is FAIL")
        elif str(h) != LEAF_HASH:
            bad.append(f"{label} = {h!r} != the champion's {LEAF_HASH!r} — "
                       "⛔ A MOVED HASH IS THE DEFECT, not the signal")
    return gate("G-LEAF", not bad,
                {"cand_leaf_hash": cand_hash, "opp_leaf_hash": opp_hash,
                 "champion": LEAF_HASH, "sense": "INVERTED (equality required)"},
                "manifest:config.{cand_leaf_hash,opp_leaf_hash}",
                ("both sides carry the champion leaf, unmoved" if not bad else
                 "⛔ G-LEAF FAILED: " + "; ".join(bad)))


def arb_off_gate(manifest: Mapping) -> dict:
    """`G-ARB-OFF` — the tie arbiter is OFF on BOTH sides.

    ⚠️ `eval_fair_puct` writes `cand_tiearb` at BOTH `config.cand_tiearb` and
    manifest top level (belt-and-braces, `eval_fair_puct.py:5099-5113`), so both
    are read. `None` is the OFF statement for the candidate; a resolved dict with
    `enabled: false` is equally OFF. `enabled: true` is the defect."""
    d = {"manifest": manifest or {}}
    v, addr = resolve(d, "manifest:config.cand_tiearb", "manifest:cand_tiearb")
    bad = []
    if v is MISSING:
        bad.append("cand_tiearb ABSENT at both addresses — ABSENT is FAIL")
    elif v is None:
        pass                                    # the positive OFF statement
    elif isinstance(v, Mapping):
        if v.get("enabled") is True:
            bad.append(f"cand_tiearb.enabled is True: {v!r} — the arbiter "
                       "overrides the search's pick at exactly the plies where "
                       "it fires, DILUTING the intervention under test")
    else:
        bad.append(f"cand_tiearb is {type(v).__name__}, not a resolved dict/None")
    # the opponent side: `fair-champion` builds from champ_cfg_dict, which
    # carries no arbiter. A PRESENT-and-enabled opponent arbiter is the defect.
    ov, oaddr = resolve(d, "manifest:config.opponent.tiearb",
                        "manifest:config.opponent.champ_cfg.tiearb")
    if isinstance(ov, Mapping) and ov.get("enabled") is True:
        bad.append(f"the OPPONENT carries an ENABLED tie arbiter at {oaddr}")
    return gate("G-ARB-OFF", not bad,
                {"cand_tiearb": None if v is MISSING else v,
                 "opponent_tiearb": None if ov is MISSING else ov,
                 "addresses": [addr, oaddr]},
                addr,
                ("the arbiter is OFF on both sides. ⚠️ A DELIBERATE DEVIATION "
                 "from the deployed champion (B=64) — deploy transfer is an "
                 "assumption (DESIGN §10.5)" if not bad else
                 "⛔ G-ARB-OFF FAILED: " + "; ".join(bad)))


def paired_gate(spec: CellSpec, records: Sequence[Mapping],
                summary: Mapping) -> dict:
    """`G-PAIRED` — the arm is deck-paired, seat-balanced, and inside its band.

    ⛔⛔ WITHOUT `--paired` THE ROUND HAS NO PRIMARY (the PG-D9 defect):
    `eval_fair_puct._build_work` returns n DISTINCT decks at ONE seat each when
    paired is false, so NO deck appears in both seatings, `n_paired == 0` on
    every arm, and the arm ALSO walks `2*n_decks` seeds — OUTSIDE its own frozen
    band. `n_common > 0` is the brief's floor; the frozen count is the real bar."""
    by_deck = _by_deck(records)
    common = per_deck_margins(records)
    bad, notes = [], []
    if not common:
        bad.append("n_common == 0 — NO deck appears in BOTH seatings. The cell "
                   "was almost certainly launched WITHOUT --paired (PG-D9).")
    if len(common) != spec.n_decks:
        bad.append(f"n_common {len(common)} != the frozen {spec.n_decks} decks")
    lo, hi = spec.seed_start, spec.seed_end
    out_of_band = sorted(s for s in by_deck if not (lo <= s <= hi))
    if out_of_band:
        bad.append(f"{len(out_of_band)} seed(s) OUTSIDE the frozen range "
                   f"[{lo}, {hi}], e.g. {out_of_band[:3]}")
    half = sorted(s for s, v in by_deck.items() if not (0 in v and 1 in v))
    if half:
        bad.append(f"{len(half)} deck(s) played at ONE SEAT ONLY, e.g. "
                   f"{half[:3]} — a deck missing a seating is DROPPED, never "
                   "zero-filled, so this is a short cell, not a balanced one")
    d = {"summary": summary or {}}
    np_, np_addr = resolve(d, "summary:n_paired")
    if np_ is not MISSING and int(np_) != len(common):
        notes.append(f"⚠️ summary.n_paired {np_} != the recomputed "
                     f"{len(common)} — RECON will price this")
    nf, _ = resolve(d, "summary:n_failed")
    if nf is MISSING:
        bad.append("summary.n_failed ABSENT — ABSENT is FAIL")
    elif int(nf) > FAILURE_RATE_VOID:
        bad.append(f"⛔ N5-FAIL: summary.n_failed = {nf}. Any failed game voids "
                   "and the read is re-run per the IS-A1 precedent.")
    return gate("G-PAIRED", not bad,
                {"n_common": len(common), "frozen_n_decks": spec.n_decks,
                 "seed_range": [lo, hi], "n_seeds_seen": len(by_deck),
                 "summary_n_paired": None if np_ is MISSING else np_,
                 "n_failed": None if nf is MISSING else nf, "notes": notes},
                np_addr or "records:seed/a_seat/diff",
                (f"{len(common)} decks, both seatings, all inside "
                 f"[{lo}, {hi}], 0 failed games" if not bad else
                 "⛔ G-PAIRED FAILED: " + "; ".join(bad)))


def crn_gate(decks_by_cell: Mapping[str, Sequence[int]], specs=None) -> dict:
    """⭐ `G-CRN` (round-level) — the three arms really did share ONE deck set.

    ⛔ P2 IS A CROSS-ARM CONTRAST. If OPP and OWN do not overlap deck-for-deck,
    `paired_contrast` silently drops to whatever intersection exists and the
    statistic the cell was funded for is not the statistic it computed. The ALL
    arm is a PREFIX SUBSET by design (400 of the 600 decks) and is checked as a
    subset, not as an equality."""
    bad = {}
    sets = {n: set(v) for n, v in decks_by_cell.items()}
    have = {n: len(s) for n, s in sets.items()}
    opp, own = sets.get("CELL_G3_OPP"), sets.get("CELL_G3_OWN")
    if opp is None or own is None:
        bad["P2"] = ("one of the two gated arms is missing — P2 does not exist "
                     "without both")
    else:
        if opp != own:
            bad["P2"] = (f"OPP and OWN deck sets DIFFER: |OPP\\OWN| = "
                         f"{len(opp - own)}, |OWN\\OPP| = {len(own - opp)}. "
                         "CRN is broken and P2 is not the funded statistic.")
        by_name = {s.name: s for s in (specs or CELLS)}
        n_want = by_name["CELL_G3_OPP"].n_decks
        if len(opp & own) != n_want:
            bad.setdefault("P2_n", f"|OPP ∩ OWN| = {len(opp & own)} != {n_want}")
    allc = sets.get("CELL_G3_ALL")
    if allc is not None and opp is not None and not allc <= opp:
        bad["ALL"] = (f"the ALL arm plays {len(allc - opp)} deck(s) outside the "
                      "shared set — it must be a PREFIX SUBSET")
    return gate("G-CRN", not bad,
                {"n_decks": have, "shared_range": list(SHARED_DECKS),
                 "problems": bad},
                "records:seed (all arms)",
                ("all three arms drew from ONE shared deck set; OPP and OWN are "
                 "deck-identical and ALL is a prefix subset" if not bad else
                 "⛔ G-CRN FAILED: " + "; ".join(f"{k}: {v}"
                                                 for k, v in bad.items())))


def n4_cost_rider(summary: Mapping) -> dict:
    """`N4-COST` — `ms_ratio_cand_over_opp` against the house 1.20 trigger.

    ⚠️ FIELD NAMES ARE A TRAP HERE (`feedback_verify_numbers_before_reporting`):
    in `eval_fair_puct`'s summary the CANDIDATE side is
    `champ_prefix_ms_per_move` and the OPPONENT side is `rung_ms_per_move`.
    ⛔ A RIDER, NEVER A VOID. Its job is to let an `S1-NEGATIVE` say of itself
    what surface A had to be told (realized 1.2116 ⇒ 'loss confounded by
    budget'). SIZING §3 predicts 1.078–1.085 for `opp`."""
    d = {"summary": summary or {}}
    cand, a1 = resolve(d, "summary:champ_prefix_ms_per_move")
    opp, a2 = resolve(d, "summary:rung_ms_per_move")
    if cand is MISSING or opp is MISSING or not opp:
        return {"ms_ratio_cand_over_opp": None, "fired": None,
                "trigger": N4_MS_RATIO_TRIGGER, "addresses": [a1, a2],
                "note": "⚠️ ABSENT — the rider cannot be evaluated and says so "
                        "rather than reading as 'did not fire'."}
    ratio = float(cand) / float(opp)
    return {"ms_ratio_cand_over_opp": ratio, "fired": ratio > N4_MS_RATIO_TRIGGER,
            "trigger": N4_MS_RATIO_TRIGGER,
            "cand_ms_per_move": float(cand), "opp_ms_per_move": float(opp),
            "addresses": [a1, a2],
            "predicted": "1.078–1.085 (SIZING §3)",
            "note": ("⛔ N4 FIRED — any loss on this arm is CONFOUNDED BY "
                     "BUDGET and must be reported as surface A's was."
                     if ratio > N4_MS_RATIO_TRIGGER else
                     "under the trigger; the arm is not budget-confounded")}


def saturation(wr) -> dict:
    lo, hi = SAT_BAND
    if wr is None:
        return {"winrate": None, "band": list(SAT_BAND), "flagged": True,
                "note": "winrate unavailable — FLAGGED, never silently OK"}
    return {"winrate": wr, "band": list(SAT_BAND), "flagged": not (lo <= wr <= hi),
            "note": "⛔ COMPANION RAIL, never a branch input. Outside the band "
                    "the deck-paired margin is compressed by the ceiling and the "
                    "elo companion is unreliable."}


# =========================================================================== #
# 7. THE LIBRARY'S OWN INVARIANTS                                              #
# =========================================================================== #

def sanity_check() -> list[str]:
    """⭐ Non-empty == the instrument is broken. `run_g3.sh` REFUSES on any
    problem, and the launcher and adjudicator share this file, so a defect here
    is a defect in BOTH."""
    p: list[str] = []
    if K_DETS * SIMS_PER_DET != TOTAL_SIMS:
        p.append(f"budget does not multiply out: {K_DETS}x{SIMS_PER_DET} != "
                 f"{TOTAL_SIMS}")
    if {c.scope for c in CELLS} != set(SCOPES):
        p.append("the three arms do not cover {opp, own, all} exactly")
    if len({c.name for c in CELLS}) != len(CELLS):
        p.append("duplicate cell name")
    if len({c.scope for c in CELLS}) != len(CELLS):
        p.append("two arms share a scope — scope is THE single variable")
    for c in CELLS:
        if c.seed_start != BAND:
            p.append(f"{c.name}: seed_start {c.seed_start} != the shared band "
                     f"{BAND} — DESIGN §6.4 requires ONE shared deck set")
        if c.n_games % 2:
            p.append(f"{c.name}: n_games {c.n_games} is not an even count of "
                     "deck-paired games")
        if c.role not in ("local", "laptop"):
            p.append(f"{c.name}: unknown role {c.role!r}")
        if c.dose != JR_DOSE or c.mask != JR_MASK:
            p.append(f"{c.name}: dose/mask drifted from the frozen "
                     f"{JR_DOSE}/{JR_MASK}")
        if THROWAWAY_BASE <= c.seed_end:
            p.append(f"{c.name} overlaps the THROWAWAY range")
    n_opp = cell_by_name("CELL_G3_OPP").n_decks
    n_own = cell_by_name("CELL_G3_OWN").n_decks
    if n_opp != n_own:
        p.append(f"the two GATED arms differ in size ({n_opp} vs {n_own}) — P2 "
                 "is a per-deck contrast and needs them equal")
    if cell_by_name("CELL_G3_ALL").n_decks > n_opp:
        p.append("the ALL control is larger than the shared set it subsets")
    if not (THROWAWAY_BASE > BAND):
        p.append("the throwaway range is not above the band")
    # the frozen power arithmetic must reproduce SIZING §4
    if abs(se_model(600) - 0.5145) > 5e-4:
        p.append(f"se_model(600) = {se_model(600):.4f} != SIZING §4's 0.514")
    if abs(se_model(400) - 0.6300) > 5e-4:
        p.append(f"se_model(400) = {se_model(400):.4f} != SIZING §4's 0.630")
    if abs(se_model_contrast(600) - 0.7275) > 1e-3:
        p.append(f"se_model_contrast(600) = {se_model_contrast(600):.4f}; "
                 "SIZING §4.1 prices D=+2 at z≈2.75, i.e. sem_D≈0.7276")
    if not (HOLM_Z[0] > NOMINAL_Z > HOLM_Z[1]):
        p.append("the nominal 2σ no longer sits inside the Holm bracket — the "
                 "READ_RULE's reconciliation of DESIGN's '≥ +2σ' shorthand is "
                 "no longer true")
    if set(BRANCH_CONSEQUENCE) != set(BRANCHES):
        p.append("a branch has no stated consequence (or vice versa)")
    if len(WITNESS_KEYS) != 3:
        p.append("the witness contract is not the three-key shape")
    return p


def branch_grid(step: float = 0.05) -> dict:
    """⭐ Every branch must be REACHABLE from some `(z_P1, z_P2, signature)`.
    A branch nobody can reach is a branch nobody has tested."""
    seen = set()
    zs = [round(-4.0 + i * step, 6) for i in range(int(8.0 / step) + 1)]
    for z1 in zs:
        for z2 in zs:
            for sig in (True, False, None):
                seen.add(branch_for_round(gates_ok=True, z_p1=z1, z_p2=z2,
                                          signature_bar_met=sig)[0])
    seen.add(branch_for_round(gates_ok=False, z_p1=0.0, z_p2=0.0,
                              signature_bar_met=True)[0])
    return {"reachable": sorted(seen), "all": sorted(BRANCHES),
            "all_reachable": set(seen) == set(BRANCHES),
            "unreachable": sorted(set(BRANCHES) - seen)}
