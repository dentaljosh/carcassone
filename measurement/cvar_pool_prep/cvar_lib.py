#!/usr/bin/env python3
"""ONE implementation of this round's cells, constants and gates.

⛔ THE PAIR IS LAW. `run_cells.sh`'s precondition ladder, `adjudicate_cvar_smoke.py`
and `test_cvar_pool.py` ALL import this module, so a launcher/adjudicator drift
is impossible by construction rather than by review. `test_cvar_pool.py` asserts
`WORKERS.conf` agrees with the constants here.

Precedent: `measurement/taup_audit_leg_20260901/cvar_lib.py` (this round is its
successor in SHAPE — two candidate-only doses, one box, deployed config both
seats — and its adjudicator is likewise the FPU family's, reused, not a copy).

⭐ THE ONE STRUCTURAL DIFFERENCE FROM EVERY PRIOR CANDIDATE-KNOB ROUND. τ_p, FPU
and c_puct all had to be gated on CONFIG alone, because nothing they did was
visible in play without a bespoke census. GT-M1 changes the ROOT PICK, so the
agent counts its own pick changes and `G-REACH` reads them out of
`summary.json`. That gate is derived from PLAY, and it is the one that can catch
the failure the config gates structurally cannot: a rule that was requested,
resolved, stamped — and never actually differed from the champion.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# =========================================================================== #
# 1. THE CELLS                                                                 #
# =========================================================================== #

#: The champion's pooling rule — the visit-weighted pooled Q = ΣW/ΣN over all
#: k worlds (`carc_core::fair::pooled_q_argmax`). BOTH SEATS carry it unless
#: `--cand-pool-mode` overrides the candidate.
POOL_MODE_PRODUCTION = "mean"

#: ⛔⛔ THE TWO DOSES, read STRAIGHT OFF the census's reach curve
#: (`measurement/cl083_mech_censuses_20260830/READOUT.md` §1, `CENSUS1.json`):
#:
#:   α      reach(α)                 marginal vs equal-weight pooling
#:   0.25   0.340  [0.277, 0.404]    0.213
#:   0.50   0.271                    0.122
#:   0.75   0.239                    0.080
#:   1.00   0.181  (= equal-weight)  0.000
#:
#:  * 0.25 — **the census's own PRIMARY and the curve's MAXIMUM**. It is the
#:    dose the survive bar (≥0.30) was cleared on, and the only dose whose CI
#:    lower end (0.277) is quoted. If risk-averse pooling does anything at all,
#:    this is where it does the most of it.
#:  * 0.50 — **the interior point**, reach 0.271, still 2.7× the census's 0.10
#:    kill bar, with the marginal risk-aversion contribution roughly HALVED
#:    (0.122 vs 0.213). It is chosen over 0.75 because 0.75's marginal
#:    contribution (0.080) is below the census's own kill bar — a dose whose
#:    risk-aversion component the census could not distinguish from inert is a
#:    dose that answers nothing.
#:
#: ⛔ NOT a ladder, and the pair is NOT a measured direction on the axis: the
#: two cells sit on DIFFERENT BANDS and CL-068 over-disperses any cross-band
#: contrast 1.8–2.2×. See PREREG §9.1.
DOSES = {"CELL_CVAR25": 0.25, "CELL_CVAR50": 0.50}


@dataclass(frozen=True)
class CellSpec:
    name: str
    alpha: float
    band: int          # ⛔ PROPOSED. See BAND_CLAIMED.placeholder.
    n_decks: int
    n_games: int


#: ⛔ PROPOSED, NOT CLAIMED — see `BAND_CLAIMED.placeholder`. The orchestrator
#: re-runs the tree sweep and appends `governance/BAND_REGISTRY.csv` (TWO rows);
#: `run_cells.sh` refuses a real chunk until the sibling `BAND_CLAIMED` exists.
#: ⚠️ 174e9 is the highest id in the registry at freeze time (SYNTH
#: mechanism-corroboration, claimed 2026-09-02), so this round starts at the
#: next monotone free id. The claiming agent RE-RUNS THE SWEEP: a band that has
#: been taken between the freeze and the claim must be REASSIGNED, which is
#: exactly what happened to this round's two predecessors (fpu_swap took 170e9
#: out from under the τ_p placeholder; the 44k rung took 173e9 out from under
#: synth-mech).
BAND_CVAR25 = 175_000_000_000
BAND_CVAR50 = 176_000_000_000
THROWAWAY_BASE = 175_999_999_000

N_DECKS = 400
N_GAMES = 800            # 400 decks x 2 seatings (deck-PAIRED, seat-balanced)

CELLS: tuple[CellSpec, ...] = (
    CellSpec("CELL_CVAR25", DOSES["CELL_CVAR25"], BAND_CVAR25, N_DECKS, N_GAMES),
    CellSpec("CELL_CVAR50", DOSES["CELL_CVAR50"], BAND_CVAR50, N_DECKS, N_GAMES),
)

#: Per-cell smoke offsets off `THROWAWAY_BASE`, so one cell's smoke can never
#: stand in for the other's. ⛔ Disjoint from the golden gate's +800 block.
SMOKE_OFFSETS = {"CELL_CVAR25": 0, "CELL_CVAR50": 100}

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
#: ⭐ W=22, the owner's standing laptop setting since 2026-09-01 (~22:40 EDT,
#: verbatim "change it at tau8. carcasum is taking 30s a turn") — the laptop
#: keeps two threads for his pinned-playout Carcasum server, which was still
#: running at this round's freeze. ⚠️ Unlike the τ_p leg's W=24 this is a
#: MEASURED operating point: the 2026-08-31 arb-on laptop sweep priced W22 at
#: 129.0 g/h at this exact cell shape, so the ETA below is a point, not a
#: bracket. W is THROUGHPUT-ONLY: games are bit-identical at any W and no gate
#: here reads a clock.
W_LAPTOP = 22
G_PER_H_LAPTOP = 129.0

# =========================================================================== #
# 3. THE BAR (PREREG §5)                                                       #
# =========================================================================== #

#: ⭐ SET AT THE EFFECT SIZE THE DECISION CARES ABOUT, NEVER AT 2·se_model
#: (owner ruling 2026-08-30). +1.0 pts/deck is the adoption class this program
#: has actually used: the two production folds it accepted are +1.229 pts/deck
#: (the k16 budget promotion) and +1.7167 pts/game (the arbiter B=64 fold), and
#: the FPU adoption chain sat on the same +1.0 with realized +1.02 / +0.86
#: judged NOT to clear. See PREREG §5 for the derivation AND for the honest
#: statement that n=400 decks can only afford the BOUNDING direction against it.
#:
#: ⚠️ NO CLOCK OFFSET IS OWED, and that is a real difference from the arbiter
#: fold. CVaR pooling costs one extra O(|legal actions|) pass per ply over
#: statistics the search already computed — it buys no sims and spends none, so
#: the bar is a pure strength bar with nothing to amortise.
BAR_M = 1.0

#: The REGRESSION bar. A rule that changes ~a third of the champion's root
#: moves is not the kind of knob that can be slightly wrong: if it is wrong it
#: should show, and a demonstrated regression CLOSES GT-M1 far more cleanly than
#: another unresolved bound. ⛔ It is NOT a "kill bar" in the census's sense —
#: the census already declined to kill on reachability — it is the
#: does-this-actively-hurt branch.
BAR_REGRESSION = 0.0

#: The instrument's realized scale on this exact shape, for the read-rule's
#: expected-distribution statement ONLY. ⛔ NOT a bar and never used as one.
#: Source: `CELL_CPUCT10` realized SE 0.6511 at n=800 paired, reproduced by both
#: τ_p cells (0.646 / 0.660).
SE_M_EXPECTED = 0.68

#: ⭐⭐ THE PLAY-DERIVED LIVENESS FLOOR (`G-REACH`). The census measured
#: reach(0.25) = 0.340 at k=8 on E4 crux plies; this round plays k=16 over whole
#: self-played games, so the realized rate is EXPECTED TO DIFFER and no bar is
#: set at the census's value. What IS asserted is that the rule REACHED AT ALL,
#: at a rate that could not be a rounding artefact of a handful of plies.
#: 0.01 is two orders of magnitude below the census's point estimate and is a
#: LIVENESS floor, not an effect-size bar: a cell below it is one whose
#: candidate is, to a good approximation, the champion.
REACH_FLOOR = 0.01


# =========================================================================== #
# 4. GATES — read the EMITTED manifest / summary, never a flag                 #
# =========================================================================== #

MISSING = object()


def dig(doc, dotted: str):
    """`doc` at a dotted address, or `MISSING`.

    ⚠️⚠️ `MISSING` IS NOT `None` — this round turns on that distinction exactly
    as the FPU family does: `config.cand_search.pool_alpha = null` is a POSITIVE
    statement ("mean pooling takes no alpha") while an ABSENT key means the
    harness PREDATES this round's plumbing and resolved nothing. No gate may
    collapse the two."""
    cur = doc
    for part in dotted.split("."):
        if not isinstance(cur, Mapping) or part not in cur:
            return MISSING
        cur = cur[part]
    return cur


def gate_pool(manifest: Mapping, want_alpha: float) -> list[str]:
    """⭐⭐ G-POOL — THE CONFIG WIRING GATE.

    No leaf hash moves on this knob, so `cand_leaf_hash` EQUALS the opponent's
    on a live cell and a moved-hash check proves nothing. The gate is the
    RESOLVED manifest, read at six addresses that must agree:

        config.cand_search.pool_mode      == "cvar"      (the REQUEST)
        config.cand_search.pool_alpha     == the dose     (the REQUEST)
        config.champion.pool_mode         == "cvar"      (the CANDIDATE's
        config.champion.pool_alpha        == the dose      resolved config)
        config.opponent.champ_cfg.pool_mode  == "mean"   (⭐⭐ THE OPPONENT)
        config.opponent.champ_cfg.pool_alpha == null

    ⛔ ABSENT IS FAIL, on every one of them.

    ⚠️ There is no `shared_pool_mode` counterpart to `shared_tau_p`, because
    there is no shared flag: pooling is candidate-only by construction. The
    opponent's rule is therefore read off the OPPONENT'S OWN resolved config,
    which is the stronger of the two witnesses anyway.
    """
    bad = []
    req_m = dig(manifest, "config.cand_search.pool_mode")
    if req_m is MISSING:
        bad.append(
            "config.cand_search.pool_mode ABSENT — ABSENT is FAIL. The harness "
            "that wrote this manifest PREDATES measurement/cvar_pool_prep, so "
            "`--cand-pool-mode` was not expressible and this cell is "
            "champion-vs-champion no matter what its dirname says.")
    elif str(req_m) != "cvar":
        bad.append(f"config.cand_search.pool_mode = {req_m!r}, want 'cvar'")

    req_a = dig(manifest, "config.cand_search.pool_alpha")
    if req_a is MISSING:
        bad.append("config.cand_search.pool_alpha ABSENT — ABSENT is FAIL")
    elif req_a is None or float(req_a) != float(want_alpha):
        bad.append(f"config.cand_search.pool_alpha = {req_a!r}, want {want_alpha!r}")

    res_m = dig(manifest, "config.champion.pool_mode")
    if res_m is MISSING:
        bad.append("config.champion.pool_mode ABSENT — ABSENT is FAIL")
    elif str(res_m) != "cvar":
        bad.append(f"config.champion.pool_mode = {res_m!r} — the CANDIDATE's "
                   "resolved config does not carry the rule")

    res_a = dig(manifest, "config.champion.pool_alpha")
    if res_a is MISSING:
        bad.append("config.champion.pool_alpha ABSENT — ABSENT is FAIL")
    elif res_a is None or float(res_a) != float(want_alpha):
        bad.append(f"config.champion.pool_alpha = {res_a!r} — the CANDIDATE's "
                   f"resolved config does not carry the dose {want_alpha!r}")

    opp_m = dig(manifest, "config.opponent.champ_cfg.pool_mode")
    if opp_m is MISSING:
        bad.append("config.opponent.champ_cfg.pool_mode ABSENT — ABSENT is FAIL")
    elif str(opp_m) != POOL_MODE_PRODUCTION:
        bad.append(
            f"⛔⛔ config.opponent.champ_cfg.pool_mode = {opp_m!r}, want "
            f"{POOL_MODE_PRODUCTION!r}. THE POOLING RULE LEAKED ONTO THE "
            "OPPONENT. There is NO shared --pool-mode flag, so this can only be "
            "a wiring defect — and both seats risk-averse is a different "
            "CHAMPION, not a candidate-only cell.")
    opp_a = dig(manifest, "config.opponent.champ_cfg.pool_alpha")
    if opp_a is MISSING:
        bad.append("config.opponent.champ_cfg.pool_alpha ABSENT — ABSENT is FAIL")
    elif opp_a is not None:
        bad.append(f"⛔⛔ config.opponent.champ_cfg.pool_alpha = {opp_a!r}, want "
                   "null — the dose LEAKED onto the opponent")
    return bad


def gate_reach(summary: Mapping) -> list[str]:
    """⭐⭐ G-REACH — THE PLAY-DERIVED WIRING GATE, and the one that makes this
    round's instrument better than its three predecessors'.

    `G-POOL` above proves the rule was REQUESTED and RESOLVED. It cannot prove
    the rule ever DIFFERED from the champion — and "the knob never bound" is
    the defect class that burned the FPU knob (a hard-coded `None` for months)
    and the phasegate smoke (adjudicated zero cells). Because GT-M1 changes the
    ROOT PICK, the agent can count its own pick changes, and this gate reads
    them:

        summary.pool.candidate.cvar_plies    > 0        (the rule DECIDED)
        summary.pool.candidate.pickchanges   > 0        (the rule REACHED)
        summary.pool.candidate.reach_in_play >= REACH_FLOOR
        summary.pool.opponent.cvar_plies    == 0        (⭐⭐ the ZERO CONTROL)
        summary.pool.opponent.mode          == "mean"
        summary.pool.candidate.modes_disagree is False  (no mid-cell rev split)

    ⛔ ABSENT IS FAIL. A summary with no `pool` block was written by a harness
    predating this round.

    ⚠️ `reach_in_play` is NOT compared to the census's `reach(α)`. The census
    measured k=8 worlds on a fixed E4 crux corpus; this counts k=16 worlds over
    whole self-played games including non-crux plies, and the two are comparable
    in KIND only. The floor is a LIVENESS floor.
    """
    bad = []
    cand = dig(summary, "pool.candidate")
    opp = dig(summary, "pool.opponent")
    if cand is MISSING or not isinstance(cand, Mapping):
        return ["summary.pool.candidate ABSENT — ABSENT is FAIL. This summary "
                "was written by a harness predating measurement/cvar_pool_prep; "
                "the cell has NO play-derived wiring witness and must VOID."]
    if opp is MISSING or not isinstance(opp, Mapping):
        bad.append("summary.pool.opponent ABSENT — ABSENT is FAIL (it is the "
                   "zero control that makes the candidate's reach readable)")
        opp = {}

    plies = cand.get("cvar_plies", MISSING)
    if plies is MISSING:
        bad.append("summary.pool.candidate.cvar_plies ABSENT — ABSENT is FAIL")
    elif int(plies) <= 0:
        bad.append(
            "summary.pool.candidate.cvar_plies == 0 — the CVaR rule decided "
            "NOTHING. The candidate pooled by the deployed mean on every ply and "
            "this cell is champion-vs-champion.")
    changes = cand.get("pickchanges", MISSING)
    if changes is MISSING:
        bad.append("summary.pool.candidate.pickchanges ABSENT — ABSENT is FAIL")
    elif int(changes) <= 0 and isinstance(plies, int) and plies > 0:
        bad.append(
            f"⛔⛔ summary.pool.candidate.pickchanges == 0 over {plies} CVaR "
            "plies — THE RULE DID NOT REACH. It was requested, resolved and "
            "stamped, and it never once disagreed with the champion. Every "
            "config gate passes such a cell; this one does not.")
    reach = cand.get("reach_in_play", MISSING)
    if reach is MISSING:
        bad.append("summary.pool.candidate.reach_in_play ABSENT — ABSENT is FAIL")
    elif float(reach) < REACH_FLOOR:
        bad.append(f"summary.pool.candidate.reach_in_play = {reach!r} < the "
                   f"liveness floor {REACH_FLOOR} — the rule reached on a "
                   "handful of plies at most, which is not a cell.")
    if cand.get("modes_disagree"):
        bad.append(
            f"summary.pool.candidate.modes_disagree is True "
            f"(modes {cand.get('modes_observed')!r}, alphas "
            f"{cand.get('alphas_observed')!r}) — the cell's games did NOT all "
            "play the same rule. That is a mid-cell source change (the "
            "cross-rev-split trap), never something to average.")
    if str(cand.get("mode")) != "cvar":
        bad.append(f"summary.pool.candidate.mode = {cand.get('mode')!r}, want "
                   "'cvar'")
    if opp:
        if int(opp.get("cvar_plies") or 0) != 0:
            bad.append(
                f"⛔⛔ summary.pool.opponent.cvar_plies = "
                f"{opp.get('cvar_plies')!r}, want 0. There is no "
                "--opp-pool-mode flag, so a CVaR-pooling opponent is a pure "
                "LEAK and the cell measures nothing.")
        if str(opp.get("mode")) not in (POOL_MODE_PRODUCTION, "MISSING"):
            bad.append(f"summary.pool.opponent.mode = {opp.get('mode')!r}, want "
                       f"{POOL_MODE_PRODUCTION!r}")
        if opp.get("modes_disagree"):
            bad.append("summary.pool.opponent.modes_disagree is True — a "
                       "mid-cell source change on the OPPONENT seat")
    return bad


def gate_singlevar(manifest: Mapping) -> list[str]:
    """G-SINGLEVAR — the pooling rule is the ONLY thing that differs between the
    seats.

    The other three members of the `cand_search` family must be OFF (null), and
    all three must be PRESENT saying so. ⛔ `fpu_reduction` is deliberately
    included even though `fpu=0.2` is a live candidate for production: it has
    not been adopted (`PRODUCTION.yaml` carries no fpu knob, and the H2H chain
    read UNRESOLVED twice), so a cell that carried it would be measuring a
    two-knob candidate against a zero-knob champion."""
    bad = []
    for key in ("fpu_reduction", "c_puct", "tau_p"):
        v = dig(manifest, f"config.cand_search.{key}")
        if v is MISSING:
            bad.append(f"config.cand_search.{key} ABSENT — ABSENT is FAIL")
        elif v is not None:
            bad.append(f"config.cand_search.{key} = {v!r} — this round is "
                       "single-variable on the pooling rule; a second live knob "
                       "makes it a confounded cell claiming one variable")
    return bad


#: ⛔ EVERY ADDRESS BELOW WAS READ OFF A REAL `manifest.json` EMITTED BY THIS
#: HARNESS (the build-time dry cell, `DEVIATIONS.md` D-1), never guessed from
#: the emitter source. The τ_p leg found three of four obvious guesses WRONG on
#: this emitter — `config.champion.sims` does not exist (it is `sims_per_det`),
#: `config.exact_k` does not exist (it is `config.endgame.exact_k`),
#: `config.backend` is a DICT (the name is `config.backend.name`) and
#: `rules_profile` is TOP-LEVEL rather than under `config`. A gate at a wrong
#: address returns MISSING and, in a lib that failed OPEN, would pass
#: vacuously — the IS-D1 defect. Here it fails closed.
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
    """G-BUDGET / G-EXACT / G-BACKEND / G-RULES — the deployed shape, both seats.

    ⚠️ `k_dets = 16` is load-bearing for THIS round in a way it was not for its
    predecessors: α is a FRACTION of k, so `ceil(0.25 * 16) = 4` worlds enter the
    lower tail here where `ceil(0.25 * 8) = 2` did in the census. A cell that
    silently ran a different width would be running a different RULE, not merely
    a different budget."""
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
    means UNARMED, which for this round is a FAIL rather than a default.

    ⚠️⚠️ THE ARBITER AND THE POOLING RULE COMPOSE, and the composition is
    deliberate: `carc_core::fair::FairAgent::pimc_move` computes the pooled pick
    FIRST and hands it to the arbiter as `champ_pick`, so on a CVaR candidate
    the arbiter arbitrates around the CVaR pick. That is the DEPLOYED agent plus
    one rule, which is what a deployed-config H2H must measure — but it means
    the two surfaces are not independently attributable in this cell, and PREREG
    §9 says so."""
    bad = []
    for side, addr in (("candidate", "config.cand_tiearb"),
                       ("opponent", "config.opp_tiearb")):
        d = dig(manifest, addr)
        if d is MISSING or not isinstance(d, Mapping):
            bad.append(f"{addr} ABSENT — the {side} seat is UNARMED; this round "
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


#: Gates that read the MANIFEST (config lives in the manifest — IS-D1).
MANIFEST_GATES = {"G-POOL": gate_pool, "G-SINGLEVAR": gate_singlevar,
                  "G-BUDGET": gate_budget, "G-ARB": gate_arbiter}
#: Gates that read SUMMARY.JSON (statistics live in the summary — IS-D1 again).
SUMMARY_GATES = {"G-REACH": gate_reach}
ALL_GATES = {**MANIFEST_GATES, **SUMMARY_GATES}


# =========================================================================== #
# 5. THE READ RULE (PREREG §6) — one implementation                            #
# =========================================================================== #

def read_branch(m: float, se: float) -> str:
    """PREREG §6's branch map, applied to a GATED cell's primary.

    ⛔ Call this ONLY after every gate in §7 passes on that cell; a failing gate
    is `P-VOID` and there is no read at all.

    One-sided 95% intervals throughout (z = 1.645), matching the FPU family."""
    lb95 = m - 1.645 * se
    ub95 = m + 1.645 * se
    if lb95 > BAR_M:
        return "P-POOLING-MOVES"
    if ub95 < BAR_REGRESSION:
        return "P-REGRESSION"
    if ub95 < BAR_M:
        return "P-BOUNDED"
    return "P-UNRESOLVED"
