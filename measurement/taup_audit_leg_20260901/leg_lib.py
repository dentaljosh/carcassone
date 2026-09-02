#!/usr/bin/env python3
"""ONE implementation of this leg's cells, constants and gates.

⛔ THE PAIR IS LAW. `run_cells.sh`'s precondition ladder, `adjudicate_smoke.py`
and `test_taup_leg.py` ALL import this module, so a launcher/adjudicator drift is
impossible by construction rather than by review. `tests` asserts `WORKERS.conf`
agrees with the constants here.

Precedent: `measurement/fpu_h2h_r2_prep/screen_lib.py` (much larger — that round
carried a full outcome adjudicator; this leg's read-out is a two-cell screen and
its adjudicator is deliberately the FPU family's, reused, not a fourth copy).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# =========================================================================== #
# 1. THE CELLS                                                                 #
# =========================================================================== #

#: The champion's prior temperature — the value BOTH SEATS carry unless
#: `--cand-tau-p` overrides the candidate. ⛔ Restated here for the launcher's log
#: line only; `run_cells.sh` RE-ASSERTS it against governance/PRODUCTION.yaml
#: (G-PROD) rather than trusting this number.
TAU_P_PRODUCTION = 5.0

#: ⛔⛔ THE TWO DOSES — BRACKETING THE DEFAULT FROM BOTH SIDES, and both INSIDE
#: T3's measured-safe interval.
#:
#:  * 3.0 — the LOW end of T3's log-uniform tau_p search space
#:    (`measurement/classical_search/OPTUNA_KNOB_SWEEP_DESIGN.md`, knob 2:
#:    "log-uniform [3.0, 8.0] … S4 bracket {3,8} flat; τ=2 known-bad (~−38); don't
#:    leave the measured-safe interval"). SHARPER priors. Chosen over anything
#:    lower precisely because τ=2 is known-bad: a dose outside the measured-safe
#:    interval would answer "is τ=2 bad?" (already known) instead of "does the
#:    axis move on the candidate side at deploy budget?".
#:  * 8.0 — the HIGH end of the same interval. SOFTER priors. It is also the
#:    direction T3's two rung-C-firing trials sat in (τ 5.42 / 5.94, both DEAD at
#:    fair transfer), so if any residual signal exists on this axis it is the side
#:    it would be on.
#:
#: ⭐ Both values have a BANKED n=200 sibling measurement (`experiments/
#: results.csv`: c5_s4_curve125_taup3 / c5_s4_curve125_taup8), so this leg's
#: numbers are directly comparable rather than free-standing.
DOSES = {"CELL_TAU3": 3.0, "CELL_TAU8": 8.0}


@dataclass(frozen=True)
class CellSpec:
    name: str
    tau_p: float
    band: int          # ⛔ PROPOSED. See BAND_CLAIMED.placeholder.
    n_decks: int
    n_games: int


#: ⛔ PROPOSED, NOT CLAIMED — see `BAND_CLAIMED.placeholder`. The orchestrator
#: re-runs the tree sweep and appends `governance/BAND_REGISTRY.csv` (TWO rows);
#: `run_cells.sh` refuses a real chunk until the sibling `BAND_CLAIMED` exists.
BAND_TAU3 = 170_000_000_000
BAND_TAU8 = 171_000_000_000
THROWAWAY_BASE = 171_999_999_000

N_DECKS = 400
N_GAMES = 800            # 400 decks x 2 seatings (deck-PAIRED, seat-balanced)

CELLS: tuple[CellSpec, ...] = (
    CellSpec("CELL_TAU3", DOSES["CELL_TAU3"], BAND_TAU3, N_DECKS, N_GAMES),
    CellSpec("CELL_TAU8", DOSES["CELL_TAU8"], BAND_TAU8, N_DECKS, N_GAMES),
)

#: Per-cell smoke offsets off `THROWAWAY_BASE`, so one cell's smoke can never
#: stand in for the other's. ⛔ Disjoint from the golden gate's +800 block.
SMOKE_OFFSETS = {"CELL_TAU3": 0, "CELL_TAU8": 100}

# =========================================================================== #
# 2. THE CELL SHAPE (both seats)                                               #
# =========================================================================== #

K_DETS = 16
SIMS_PER_DET = 1376
TOTAL_SIMS = 22016
EXACT_K = 2
EXACT_MODE = "marginalized"
BACKEND = "rust"
RULES_PROFILE = "fixed_v1"
CARCASSONNE_FIX_R9 = "1"

#: THE TIE ARBITER — ARMED, BOTH SEATS, at the deployed spec. Verbatim from
#: `measurement/fpu_h2h_r2_prep/WORKERS.conf`; `run_cells.sh` RE-ASSERTS against
#: governance/PRODUCTION.yaml at launch (G-PROD).
TIEARB = {"B": 64, "J": 4, "mode": "argmax", "salt": "tiearb2-deploy-v1",
          "eps": 0.0, "phase_gate": "all"}

BOX = "laptop"
W_LAPTOP = 22  # 24 for CELL_TAU3, 22 for CELL_TAU8 (owner order, D-6); W is result-invariant            # owner threads ruling 2026-09-01 ("32 and 24")

# =========================================================================== #
# 3. THE BAR (READ_RULE / PREREG §5)                                           #
# =========================================================================== #

#: ⭐ SET AT THE EFFECT SIZE THE DECISION CARES ABOUT, NEVER AT 2·se_model
#: (owner ruling 2026-08-30). +1.0 pts/deck is the adoption-relevant effect the
#: FPU chain used; see PREREG §5 for the derivation AND for the honest statement
#: that n=400 decks can only afford the BOUNDING direction against it.
BAR_M = 1.0

#: The instrument's realized scale, for the read-rule's expected-distribution
#: statement only. ⛔ NOT a bar and never used as one.
SE_M_EXPECTED = 0.68


# =========================================================================== #
# 4. GATES — read the EMITTED manifest, never a flag                           #
# =========================================================================== #

MISSING = object()


def dig(doc, dotted: str):
    """`doc` at a dotted address, or `MISSING`.

    ⚠️⚠️ `MISSING` IS NOT `None` — this leg turns on that distinction exactly as
    the FPU family does: `config.cand_search.tau_p = null` is a POSITIVE statement
    ("the shared --tau-p") while an ABSENT key means the harness PREDATES this
    leg's plumbing and resolved nothing. No gate may collapse the two."""
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


def gate_taup(manifest: Mapping, want_tau: float) -> list[str]:
    """⭐⭐ G-TAUP — THE WIRING GATE, and the whole reason this leg exists.

    No leaf hash moves on this knob, so `cand_leaf_hash` EQUALS the opponent's on
    a live cell and a moved-hash check proves nothing. The gate is therefore the
    RESOLVED manifest, read at four addresses that must agree pairwise:

        config.cand_search.tau_p          == the dose   (the REQUEST)
        config.champion.tau_p             == the dose   (the CANDIDATE's resolved
                                                         HeuristicPriorConfig)
        config.cand_search.shared_tau_p   == 5.0        (the SHARED flag)
        config.opponent.champ_cfg.tau_p   == 5.0        (⭐⭐ THE OPPONENT — the
                                                         proposition --tau-p fails)

    ⛔ ABSENT IS FAIL, on every one of them.
    """
    bad = []
    req = dig(manifest, "config.cand_search.tau_p")
    if req is MISSING:
        bad.append(
            "config.cand_search.tau_p ABSENT — ABSENT is FAIL. The harness that "
            "wrote this manifest PREDATES measurement/taup_audit_leg_20260901, so "
            "`--cand-tau-p` was not expressible and this cell is "
            "champion-vs-champion no matter what its dirname says.")
    elif req is None or float(req) != float(want_tau):
        bad.append(f"config.cand_search.tau_p = {req!r}, want {want_tau!r}")

    res = dig(manifest, "config.champion.tau_p")
    if res is MISSING:
        bad.append("config.champion.tau_p ABSENT — ABSENT is FAIL")
    elif float(res) != float(want_tau):
        bad.append(f"config.champion.tau_p = {res!r} — the CANDIDATE's resolved "
                   f"config does not carry the dose {want_tau!r}")

    shared = dig(manifest, "config.cand_search.shared_tau_p")
    if shared is MISSING:
        bad.append("config.cand_search.shared_tau_p ABSENT — ABSENT is FAIL")
    elif float(shared) != TAU_P_PRODUCTION:
        bad.append(f"config.cand_search.shared_tau_p = {shared!r}, want the "
                   f"champion's {TAU_P_PRODUCTION!r}")

    opp = dig(manifest, "config.opponent.champ_cfg.tau_p")
    if opp is MISSING:
        bad.append("config.opponent.champ_cfg.tau_p ABSENT — ABSENT is FAIL")
    elif float(opp) != TAU_P_PRODUCTION:
        bad.append(
            f"⛔⛔ config.opponent.champ_cfg.tau_p = {opp!r}, want "
            f"{TAU_P_PRODUCTION!r}. THE DOSE LEAKED ONTO THE OPPONENT — this is "
            "the exact defect --cand-tau-p was built to make impossible, and a "
            "cell with it is a two-sided knob change wearing a candidate-only "
            "cell's name.")
    return bad


def gate_singlevar(manifest: Mapping) -> list[str]:
    """G-SINGLEVAR — tau_p is the ONLY thing that differs between the seats.

    The other two members of the `cand_search` family must be OFF (null), and
    both must be PRESENT saying so."""
    bad = []
    for key, want in (("fpu_reduction", None), ("c_puct", None)):
        v = dig(manifest, f"config.cand_search.{key}")
        if v is MISSING:
            bad.append(f"config.cand_search.{key} ABSENT — ABSENT is FAIL")
        elif v is not want:
            bad.append(f"config.cand_search.{key} = {v!r} — this leg is "
                       "single-variable on tau_p; a second live knob makes it a "
                       "confounded cell claiming one variable")
    return bad


#: ⛔ EVERY ADDRESS BELOW WAS READ OFF A REAL `manifest.json` EMITTED BY THIS
#: HARNESS (the build-time dry cell, `DEVIATIONS.md` D-1), never guessed from the
#: emitter source. Three of the four obvious guesses are WRONG on this emitter —
#: `config.champion.sims` does not exist (it is `sims_per_det`), `config.exact_k`
#: does not exist (it is `config.endgame.exact_k`), `config.backend` is a DICT
#: (the name is `config.backend.name`) and `rules_profile` is TOP-LEVEL, not
#: under `config`. A gate at a wrong address returns MISSING and, in a lib that
#: failed OPEN, would pass vacuously — the IS-D1 defect. Here it fails closed,
#: which is why the dry cell had to exist before this list was written.
BUDGET_CHECKS = (
    ("config.champion.k_dets", K_DETS),
    ("config.champion.sims_per_det", SIMS_PER_DET),
    ("config.champion.total_sims", TOTAL_SIMS),
    ("config.opponent.k_dets", K_DETS),
    ("config.opponent.sims_per_det", SIMS_PER_DET),
    ("config.opponent.total_sims", TOTAL_SIMS),
    ("config.endgame.exact_k", EXACT_K),
    ("config.endgame.mode", EXACT_MODE),
    ("config.opponent.endgame.exact_k", EXACT_K),
    ("config.opponent.endgame.mode", EXACT_MODE),
    ("config.backend.name", BACKEND),
    ("rules_profile.name", RULES_PROFILE),
    ("config.paired", True),
    ("config.seatings_per_deck", 2),
)


def gate_budget(manifest: Mapping) -> list[str]:
    """G-BUDGET / G-EXACT / G-BACKEND / G-RULES — the deployed shape, both seats."""
    bad = []
    for addr, want in BUDGET_CHECKS:
        v = dig(manifest, addr)
        if v is MISSING:
            bad.append(f"{addr} ABSENT — ABSENT is FAIL")
        elif str(v) != str(want):
            bad.append(f"{addr} = {v!r}, want {want!r}")
    return bad


def gate_arbiter(manifest: Mapping) -> list[str]:
    """G-ARB — the deployed arbiter, ARMED on BOTH seats, at the deployed dict.

    ⚠️ The opponent block is ABSENT-when-unarmed by design (eval_fair_puct's
    deliberate inverse of `cand_tiearb`'s always-present rule), so ABSENT here
    means UNARMED, which for this leg is a FAIL rather than a default."""
    bad = []
    for side, addr in (("candidate", "config.cand_tiearb"),
                       ("opponent", "config.opp_tiearb")):
        d = dig(manifest, addr)
        if d is MISSING or not isinstance(d, Mapping):
            bad.append(f"{addr} ABSENT — the {side} seat is UNARMED; this leg "
                       "runs the DEPLOYED config, which includes the arbiter")
            continue
        if not d.get("enabled"):
            bad.append(f"{addr}.enabled is falsy — the {side} seat is UNARMED")
        for k, want in (("B", TIEARB["B"]), ("J", TIEARB["J"]),
                        ("mode", TIEARB["mode"]), ("salt", TIEARB["salt"]),
                        ("eps", TIEARB["eps"]),
                        ("phase_gate", TIEARB["phase_gate"])):
            got = d.get(k, MISSING)
            if got is MISSING or str(got) != str(want):
                bad.append(f"{addr}.{k} = {got!r}, want {want!r}")
    return bad


ALL_GATES = {"G-TAUP": gate_taup, "G-SINGLEVAR": gate_singlevar,
             "G-BUDGET": gate_budget, "G-ARB": gate_arbiter}
