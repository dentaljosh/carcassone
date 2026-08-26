#!/usr/bin/env python3
"""INVASION-RISK TERM FAMILY — ROUND-1 SCREEN AT 2752 — THE SHARED BAR LIBRARY.

⛔ **THIS FILE IS THE ONE IMPLEMENTATION OF EVERY BAR, EVERY CONSTANT AND EVERY
COST FIGURE THIS PAIR USES.** `READ_RULE.md` §7:

    "Every bar and every constant lives in `screen_lib.py`, imported by both the
     adjudicator and the launcher's precondition ladder, so the launcher's
     in-flight `IDENT` pre-check and the adjudicator's `G-IDENT` cannot drift
     apart. The launcher pins ONLY the band as a numeric literal and asserts it
     equals `screen_lib.BAND`; every other constant is read from the library."

WHY THIS FILE EXISTS AT ALL — the defect it is built against
============================================================
`measurement/track_d2r2_prep` shipped a live burn-in gate and a post-hoc
adjudication gate that were two *different implementations of the same
proposition*, and they disagreed: the quantity the pilot measured was not the
quantity the cell realized, and the pair died at `G-TIMING` after ~44 core-h.
Attempt 3's fix — carried forward by `track_d2r4_prep/d2r4_lib.py` and adopted
here — was to make the LIVE gate and the POST-HOC gate **literally the same
code**.

This pair has exactly that shape: `DESIGN.md` §6.4 requires the launcher to
refuse to start `A_MID` / `B_MID` / `D_MID` until `IDENT`'s archive passes its
bar, and `READ_RULE.md` §3 `G-IDENT` re-asks the same question after the fact.
`ident_gate()` below is that one implementation. The launcher calls it through a
`python -c` / heredoc; the adjudicator imports it. Neither re-types a bar.

⚠️ **STDLIB ONLY, DELIBERATELY.** Nothing here imports `carcassonne_ai`,
`eval_fair_puct`, numpy or the rust bindings. The launcher's precondition ladder
runs this module *before* the wheel has been proven fresh — a library that
needed the harness to import would be unusable at exactly the moment it is most
needed, and would make a stale-wheel diagnosis depend on the stale wheel.

⚠️ **`paired_margin()` IS A DELIBERATELY INDEPENDENT RE-IMPLEMENTATION** of
`eval_fair_puct._paired_z`, NOT an import of it. `READ_RULE.md` §3 `RECON` says
so in as many words: the witness is "recomputed from scratch from the raw
`seed*_a*.json` records by an independent re-implementation in `screen_lib.py`".
An imported `_paired_z` would witness nothing — it would agree with the analyzer
by construction. (This is the ONE place this pair deliberately diverges from
`track_d2r4_prep/analyze_d2r4.py`, which imports `_paired_z` because ITS
READ_RULE names the harness function as the convention of record. Ours names an
independent recomputation as the WITNESS. Both are right for their own pair.)

⛔ **NOTHING IN THIS FILE MOVES AFTER THE BLIND COMMIT.** Every number below
exists before any game does. A launcher or an adjudicator that disagrees with
`READ_RULE.md` is a code defect; the pair does not move.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

# --------------------------------------------------------------------------- #
# THE BAND (DESIGN.md §5)                                                       #
#                                                                               #
# The all-branches sweep of 2026-08-26 (139 refs / 641 registry-and-claim files) #
# found 151000000000 free everywhere. `WORKERS.conf` pins the same integer as    #
# its ONE numeric literal and                                                    #
# `tests/test_invasion_screen_instrument.py::test_workers_conf_band_matches...`  #
# asserts the two agree — a launcher that drifts from the pair is a launcher     #
# defect.                                                                        #
# --------------------------------------------------------------------------- #
BAND = 151000000000

# --------------------------------------------------------------------------- #
# THE LEAF (DESIGN.md §2.2, READ_RULE.md §3 G-LEAF)                             #
#                                                                               #
# ⚠️ THE ASYMMETRY IS LOAD-BEARING. An explicit-ZERO invasion config hashes AS   #
# the champion, because the hash names the leaf FUNCTION and a zero-weight       #
# config IS the champion leaf bit-for-bit (`_LEAF_HASH_EXCLUDE_IF_DEFAULT` in    #
# `scripts/classical_search/c5_leaf_override.py` drops every invasion field      #
# while it holds its default). A NONZERO weight must move the hash. So `IDENT`   #
# runs under the STRICT hash assertion and passes it, while A/B/D need           #
# `--allow-leaf-hash-drift`; `G-LEAF(c)` gates the asymmetry in BOTH directions. #
# --------------------------------------------------------------------------- #
PROD_LEAF_HASH = "a36d2e15a3b3d71d"          # == governance/PRODUCTION.yaml champion
CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)

#: Every field of the invasion family, and the value each holds when the term is
#: OFF. `_leaf_dict` DROPS a field while it holds its default, so in a manifest
#: "absent" IS "default" and both readings must pass (READ_RULE §3 G-INVASION).
#: ⚠️ `invasion_alpha_cap == 0.0` means UNCAPPED in this family (an explicit
#: compare, not a sentinel bug) — which is why B_MID's frozen cap is 11.0 and
#: never 0.0, and why `G-CAPFWD` exists at all (DESIGN §3.2a).
INVASION_DEFAULTS: dict[str, float | int] = {
    "invasion_beta": 0.0,
    "invasion_alpha": 0.0,
    "invasion_alpha_cap": 0.0,
    "invasion_stub_max_tiles": 2,
    "invasion_gamma": 0.0,
    "invasion_delta_farm": 0.0,
}
INVASION_FIELDS = tuple(INVASION_DEFAULTS)


# --------------------------------------------------------------------------- #
# THE FOUR CELLS (DESIGN.md §3, §5.1)                                           #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CellSpec:
    """One cell of round 1. Every field is frozen by `DESIGN.md`; nothing here is
    chosen by this file."""

    name: str                       # IDENT | A_MID | B_MID | D_MID
    seed_start: int                 # first deck seed of this cell's OWN range
    n_decks: int                    # frozen deck count (G-BAND, G-DECKS, G-N)
    n_games: int                    # == 2 * n_decks (deck-paired, both seatings)
    out_subdir: str                 # archive dirname under the run root
    leaf_json: str                  # the --cand-leaf-json this cell runs
    cand_leaf_hash: str             # G-LEAF(c): the pinned candidate leaf hash
    invasion_keys: frozenset        # G-SINGLEVAR(b): the EXACT frozen key set
    invasion_values: Mapping        # G-INVASION: knob -> frozen value
    allow_leaf_hash_drift: bool     # DESIGN §2.2: the launcher's flag asymmetry
    role: str = "arm"               # "precondition" for IDENT, "arm" for A/B/D

    @property
    def seed_end(self) -> int:
        """Inclusive last deck seed of this cell's own disjoint range."""
        return self.seed_start + self.n_decks - 1

    @property
    def seeds(self) -> range:
        return range(self.seed_start, self.seed_start + self.n_decks)

    def in_range(self, seed: int) -> bool:
        return self.seed_start <= int(seed) <= self.seed_end


#: ⛔ ORDERED, cheapest-informative-first (DESIGN §6.4): IDENT runs FIRST AND
#: ALONE because it is a PRECONDITION on the other three — if the wiring is
#: broken it is found for 8 core-h instead of 62. The launcher enforces the
#: order; the adjudicator adjudicates in it.
CELLS: tuple[CellSpec, ...] = (
    CellSpec(
        name="IDENT",
        seed_start=151000000000, n_decks=200, n_games=400,
        out_subdir="ident", leaf_json="leaf_ident.json",
        cand_leaf_hash="a36d2e15a3b3d71d",
        # ∅ — the explicit zeros are dropped by `_leaf_dict`'s default-exclusion,
        # so cand_leaf_cfg and opp_leaf_cfg are IDENTICAL dicts (READ_RULE §3.3b).
        invasion_keys=frozenset(),
        invasion_values={},
        # ⛔ WITHHELD ON IDENT, DELIBERATELY (DESIGN §2.2). A zero-weight config
        # hashes AS the champion, so IDENT passes the STRICT, un-relaxed
        # `_assert_netprior_leaf`. A drift flag here would be a launcher defect
        # the adjudicator can see in the manifest.
        allow_leaf_hash_drift=False,
        role="precondition",
    ),
    CellSpec(
        name="A_MID",
        seed_start=151000000200, n_decks=400, n_games=800,
        out_subdir="a_mid", leaf_json="leaf_a_mid.json",
        cand_leaf_hash="0fd1680fa363d65e",
        invasion_keys=frozenset({"invasion_beta"}),
        invasion_values={"invasion_beta": 0.12},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="B_MID",
        seed_start=151000000600, n_decks=400, n_games=800,
        out_subdir="b_mid", leaf_json="leaf_b_mid.json",
        cand_leaf_hash="42adadc988784b44",
        # ⚠️ TWO keys, not one: the cap travels with alpha. `rust_agent.
        # leaf_config_rs` forwards `invasion_alpha_cap` ONLY when
        # `invasion_alpha != 0.0` (DESIGN §2.3), so a cell that set a cap without
        # an alpha would have it silently dropped by the rust config while the
        # manifest still showed it — a manifest that LIES about the running leaf.
        # `G-CAPFWD` asserts the biconditional on every cell.
        invasion_keys=frozenset({"invasion_alpha", "invasion_alpha_cap"}),
        invasion_values={"invasion_alpha": 0.09, "invasion_alpha_cap": 11.0},
        allow_leaf_hash_drift=True,
    ),
    CellSpec(
        name="D_MID",
        seed_start=151000001000, n_decks=400, n_games=800,
        out_subdir="d_mid", leaf_json="leaf_d_mid.json",
        cand_leaf_hash="5012569b4e93d559",
        invasion_keys=frozenset({"invasion_delta_farm"}),
        invasion_values={"invasion_delta_farm": 0.12},
        allow_leaf_hash_drift=True,
    ),
)

CELL_NAMES = tuple(c.name for c in CELLS)
IDENT_CELL = CELLS[0]
#: The three ARMS. `PROMOTE` / `BRACKET` / `REVERSED` fire on these and never on
#: IDENT, which is a precondition and not a fifth result (DESIGN §3.1).
ARM_CELLS = tuple(c for c in CELLS if c.role == "arm")


def cell_by_name(name: str) -> CellSpec:
    for c in CELLS:
        if c.name == name:
            return c
    raise KeyError(f"no such cell: {name!r} (have {list(CELL_NAMES)})")


# --------------------------------------------------------------------------- #
# THE §9 SMOKE LEG (DESIGN.md §9)                                               #
#                                                                               #
# 16 games (8 decks x 2 seatings) on a THROWAWAY range deliberately placed far   #
# above every cell range, so no arithmetic slip can reach a real deck. The smoke #
# runs B_MID's config because B is the cell with the most plumbing to break: a   #
# nonzero weight, the drift flag, AND the cap-forwarding biconditional.          #
# It is DISCARDED, never pooled, never claimed, never adjudicated as a result.   #
# --------------------------------------------------------------------------- #
SMOKE_SEED_START = 151999999000
SMOKE_DECKS = 8
SMOKE_GAMES = 16
SMOKE_CELL = "B_MID"


# --------------------------------------------------------------------------- #
# THE BARS (READ_RULE.md §3, §4)                                                #
#                                                                               #
# ⛔ Each is written the way READ_RULE writes it, and the comparison operators   #
# in `branch_for_cell()` / `ident_gate()` are the ones READ_RULE uses — `>=`,    #
# `<=`, `<`. A bar is a CLOSED interval at exactly its stated endpoint; the      #
# instrument tests drive each one AT the endpoint for that reason.               #
# --------------------------------------------------------------------------- #
PROMOTE_Z = 2.0          # §4 PROMOTE:  z_C >= +2.0
BRACKET_Z = 1.0          # §4 BRACKET:  +1.0 <= z_C < +2.0
REVERSED_Z = -2.0        # §4 REVERSED: z_C <= -2.0
IDENT_ABS_Z_MAX = 2.0    # §3 G-IDENT:  |z_IDENT| <= 2.0

#: §3 G-SAT — a RAIL check, not a strength bar. Both arms are the same champion
#: differing by one leaf term; a win-rate outside this window means the two sides
#: are not the agents this design says they are, and the margin would be a rail
#: reading rather than a measurement.
SAT_WR = (0.35, 0.65)

#: §3 G-N — `n_common >= 80%` of the frozen deck count.
N_COMMON_FRAC = 0.80

#: §3 G-N — a failure rate STRICTLY BELOW 2% is REPORTED, not silently absorbed,
#: and does not by itself void (the `b32v64` 0.100% rust-panic-class precedent).
#: At or above 2% the cell voids.
FAILURE_RATE_VOID = 0.02

#: §2.1 / DESIGN §4.1 — the sizing model, read off seven n=400-deck deck-paired
#: fixed_v1+R9 rust cells already in experiments/results.csv (median 13.15,
#: closest analogue b119e9 13.60, MAX 14.67). This pair sizes on the MAX: a false
#: positive from an underpowered screen is the worse failure mode, and this
#: screen's whole job is to decide what gets funded next.
#: ⛔ POWER ARITHMETIC ONLY. Every bar in §4 is evaluated at the cell's OWN
#: REALIZED SE; this constant is NEVER a denominator in a branch test.
SIGMA_D_MODEL = 14.67

#: §1 — realized/modelled SE outside this window is FLAGGED as a dispersion
#: anomaly. Reported, never a branch input.
SE_ANOMALY_BAND = (0.70, 1.43)

#: §4.4 — the in-family elo/pt bracket. Endpoints are two in-family cells:
#: `cl060_h2h_k8x1376_vs_deploy_k4x688` (16.74) and
#: `width_k4x2752_..._b119e9` (19.35). Importing another cell's EFFECT SIZE is
#: forbidden; a UNIT CONVERSION whose endpoints are both stated, both in-family,
#: and carried as a visible range is the honest alternative to dividing by ~zero.
ELO_PER_PT_BRACKET = (16.74, 19.35)

#: §3 RECON tolerance: rel 1e-6 / abs 1e-9 on every checked statistic.
RECON_RTOL = 1e-6
RECON_ATOL = 1e-9

#: §3.5 — THE SMOKE LEG'S PINNED ALLOWED SET. A 16-game throwaway archive on a
#: disjoint range cannot satisfy these BY CONSTRUCTION. A failure OUTSIDE this
#: set is a LAUNCH BLOCKER, not a readout surprise: a gate that cannot read what
#: the harness EMITS has to be found before 2800 games are spent, not after.
#: ⚠️ `RECON/n_paired` is a SUB-CHECK id, not a gate id — RECON is decomposed per
#: statistic precisely so this one entry cannot excuse a margin/z/winrate/elo
#: disagreement.
SMOKE_ALLOWED_FAILURES = frozenset({
    "G-BAND", "G-DECKS", "G-N", "G-SAT", "G-IDENT", "RECON/n_paired",
})

#: Why each member of the allowed set cannot pass on a 16-game throwaway. Printed
#: by `--smoke-mode` so the allowed set is auditable and cannot quietly widen.
SMOKE_ALLOWED_REASONS = {
    "G-BAND": "the smoke runs on the DISJOINT throwaway range "
              f"({SMOKE_SEED_START}..{SMOKE_SEED_START + SMOKE_DECKS - 1}) with "
              f"{SMOKE_DECKS} decks, never a cell's claimed band/deck count.",
    "G-DECKS": "same reason: every realized seed is outside every cell's own "
               "range, and n_common is 8, not 200/400.",
    "G-N": f"a smoke is {SMOKE_GAMES} games, not 400/800.",
    "G-SAT": "a 16-game winrate is a property of the DATA at a sample size that "
             "cannot establish a saturation property; a smoke must not be able "
             "to block a launch on a coin flip.",
    "G-IDENT": "there is no IDENT cell in a single-cell smoke archive, and the "
               "round-level identity bar is not askable of one.",
    "RECON/n_paired": "the deck-count half of the reconciliation is a band "
                      "property; the MARGIN/z/winrate/elo halves are NOT allowed "
                      "to fail and are enforced separately.",
}

#: The 18 gate ids of READ_RULE §3, in the order the readout prints them.
GATE_IDS = (
    "G-BAND", "G-DECKS", "G-SINGLEVAR", "G-LEAF", "G-INVASION", "G-CAPFWD",
    "G-WHEEL", "G-RULES", "G-BACKEND", "G-BUDGET", "G-TIEARB", "G-EXACT",
    "G-REV", "G-BLIND", "G-N", "G-SAT", "G-IDENT", "RECON",
)
assert len(GATE_IDS) == 18, "READ_RULE §3 names EIGHTEEN gates"

#: The statistics `RECON` reconciles, in print order. Each becomes a sub-check id
#: `RECON/<stat>`.
RECON_STATS = ("paired_mean_margin", "paired_z", "n_paired", "winrate", "elo")


# --------------------------------------------------------------------------- #
# THE COST MODEL (DESIGN.md §6.1, §6.2)                                         #
#                                                                               #
# ⛔ USE THE TWO-POINT FIT, NOT A LINEAR PER-SIM RATE. The per-move cost has a    #
# ~160 ms FIXED component, so a naive 0.159 ms/sim x 2752 under-prices by ~11%.  #
# Inputs are MEASURED, from track_d2r4_prep's tenancy-enforced clean window:     #
#     652.5 ms/move at k4x1024 = 4096 total sims, W=22, exclusive                #
#     => c = (652.5 - 160) / 4096 = 0.12025 ms per total-sim                     #
#     => @2752: 160 + 331 = 491 ms/move                                          #
# ⚠️ Do NOT price this off `experiments/results.csv fair_ruler_rebase_2752` —     #
# that row is a PYTHON-backend cell (1.116 ms per total-sim, 7x the rust figure) #
# and `track_d2r2_prep/DESIGN.md:401-406` forbids transferring its absolutes to  #
# a rust cell. Cited here only to record that it was checked and rejected.       #
# --------------------------------------------------------------------------- #
MS_PER_MOVE_FIXED = 160.0     # the fixed per-move component of the two-point fit
MS_PER_SIM = 0.12025          # the marginal cost per TOTAL sim
MOVES_PER_SIDE = 69.0         # measured, rust, fixed_v1
OVERHEAD = 1.06               # harness/solver overhead (d2r4 realized 89.09 vs 83.8)
W_UTIL = 0.84                 # W-utilisation at W=22 on the 5900XT (conservative)

#: DESIGN §6.2's named uncertainty. THE CANDIDATE-SIDE INVASION ARITHMETIC IS
#: UNMEASURED: the four shapes add a per-component scan (and for shape B an
#: ordered-pair scan) on top of a `decompose` the leaf already pays for, charged
#: to the CANDIDATE SIDE ONLY (the opponent's weights are all 0.0, so the gated
#: statements are skipped). The honest range is 0% to +50% ON THE CANDIDATE HALF.
#: ⚠️ DESIGN §6.2's table is computed at +25% on the candidate half (= +12.5% per
#: game): 800 games x 71.81 s x 1.125 = 17.96 core-h, which is the table's 18.0.
#: The prose's "0% to +25% per game" is the SAME knob stated per-game rather than
#: per-half — the two readings differ by a factor of two and the table is the
#: one this function reproduces.
CAND_MARGIN_TABLE = 0.25      # the DESIGN §6.2 column
CAND_MARGIN_MAX = 0.50        # the upper end of the honest range


def ms_per_move(total_sims: int = 2752) -> float:
    """DESIGN §6.1's two-point fit: `ms/move(N) = 160 + 0.12025 * N`."""
    return MS_PER_MOVE_FIXED + MS_PER_SIM * float(total_sims)


def project_cost(n_games: int, total_sims: int = 2752, w: int = 22,
                 cand_margin: float = 0.0) -> dict:
    """DESIGN §6.1/§6.2's cost projection. Used by the launcher's `--dry-run` to
    print an ETA before anything is spent, and by §4.3 item 6 to sit beside the
    REALIZED core-hours.

    `cand_margin` scales the CANDIDATE HALF ONLY (see `CAND_MARGIN_TABLE`).
    At `cand_margin=0` this returns the §6.1 BASE figure, ~71.8 s/game.
    """
    per_side_s = MOVES_PER_SIDE * ms_per_move(total_sims) / 1000.0
    s_per_game = (per_side_s * (1.0 + float(cand_margin)) + per_side_s) * OVERHEAD
    core_s = s_per_game * int(n_games)
    wall_s = core_s / (float(w) * W_UTIL) if w else float("nan")
    return {
        "n_games": int(n_games),
        "total_sims": int(total_sims),
        "cand_margin": float(cand_margin),
        "ms_per_move": ms_per_move(total_sims),
        "s_per_side": per_side_s,
        "s_per_game": s_per_game,
        "core_hours": core_s / 3600.0,
        "wall_hours": wall_s / 3600.0,
        "wall_minutes": wall_s / 60.0,
        "w": int(w),
        "w_util": W_UTIL,
    }


def project_round_cost(w: int = 22, cand_margin: float = 0.0) -> dict:
    """The whole round, cell by cell. `IDENT` never carries the invasion margin —
    BOTH its sides are weight-0, so there is no invasion arithmetic at all."""
    per_cell, core = {}, 0.0
    for c in CELLS:
        m = 0.0 if c.name == "IDENT" else cand_margin
        p = project_cost(c.n_games, w=w, cand_margin=m)
        per_cell[c.name] = p
        core += p["core_hours"]
    return {"per_cell": per_cell, "core_hours": core,
            "wall_hours": core / (float(w) * W_UTIL) if w else float("nan"),
            "cand_margin": float(cand_margin)}


# --------------------------------------------------------------------------- #
# THE STATISTIC (READ_RULE.md §1) — the WITNESS implementation                  #
# --------------------------------------------------------------------------- #
def _by_deck(records: Iterable[Mapping]) -> dict[int, dict[int, float]]:
    """`{seed: {a_seat: diff}}` over records that carry all three fields.

    A record missing `seed`, `a_seat` or `diff` is DROPPED here and shows up as a
    short `n_paired` at the gate — it is never silently defaulted to zero.
    """
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
    """`D(d) = (diff(d, a_seat=0) + diff(d, a_seat=1)) / 2`, over decks that
    appear in BOTH seatings. A deck missing a seating is DROPPED — READ_RULE §1,
    and `eval_fair_puct._paired_z`'s own `if 0 in v and 1 in v`.

    `diff` is the harness's own final-score margin, CANDIDATE minus OPPONENT, in
    POINTS (`eval_fair_puct.py:1603`). Sign: `D > 0` ⇒ the invasion term WON.
    """
    return {s: (v[0] + v[1]) / 2.0
            for s, v in sorted(_by_deck(records).items()) if 0 in v and 1 in v}


def paired_margin(records: Iterable[Mapping]):
    """READ_RULE §1's statistic, recomputed from scratch off the raw records.

    Returns `(mean, z, n_paired, se, per_deck_list)`.

    Identical in construction to `eval_fair_puct._paired_z` (`2371-2383`):
    per-deck seat-balanced margin, SAMPLE stdev (ddof=1), `se = sd/sqrt(n)`,
    `z = mean/se`. Fewer than two paired decks ⇒ `(None, None, n, None, list)`,
    mirroring `_paired_z`'s own `if len(ds) < 2` guard — a one-deck cell has no
    dispersion and must not be handed a z of any kind.

    ⚠️ Accumulated with `math.fsum` rather than `sum` DELIBERATELY: the point of
    a witness is to be a different computation, and `RECON`'s rel-1e-6 tolerance
    is wide enough to absorb the summation-order difference while staying far
    tighter than any real defect.
    """
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
    """`eval_fair_puct._summary`'s W/D/L, winrate and elo, recomputed from the raw
    records (`2574-2586`).

        wr   = (W + 0.5 D) / n
        elo  = 400 * log10(wr / (1 - wr))
        sig  = (400/ln10) * sqrt(wr(1-wr)/n) / (wr(1-wr))

    Wins come from the record's own `won_by_champ`, draws from `drew` — NOT from
    re-deriving them from `diff`, because the W/D/L classification moves under the
    WC tie rule while `diff` does not, and this pair does not run that rule.
    A degenerate winrate of exactly 0 or 1 gets `elo = ±800` (the harness's own
    `copysign(800, wr-0.5)`) and `sig = nan`.
    """
    scored = [r for r in records if isinstance(r, Mapping) and "diff" in r]
    n = len(scored)
    w = sum(1 for r in scored if r.get("won_by_champ") is True)
    d = sum(1 for r in scored if r.get("drew") is True)
    losses = n - w - d
    if n == 0:
        return {"n": 0, "W": 0, "D": 0, "L": 0, "winrate": None,
                "elo": None, "elo_sig_1sigma": None, "avg_diff": None}
    wr = (w + 0.5 * d) / n
    if 0.0 < wr < 1.0:
        elo = 400.0 * math.log10(wr / (1.0 - wr))
        sig = (400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n) / (wr * (1 - wr))
    else:
        elo, sig = math.copysign(800.0, wr - 0.5), float("nan")
    return {"n": n, "W": w, "D": d, "L": losses, "winrate": wr,
            "elo": elo, "elo_sig_1sigma": sig,
            "avg_diff": math.fsum(float(r["diff"]) for r in scored) / n}


def recon_close(a, b) -> bool:
    """READ_RULE §3 RECON tolerance: rel 1e-6 / abs 1e-9.

    `None` closes only to `None`: an analyzer field that is genuinely absent must
    witness absent too, not merely small. ABSENT is FAIL, never a skip.
    """
    if a is None or b is None:
        return a is None and b is None
    try:
        af, bf = float(a), float(b)
    except (TypeError, ValueError):
        return a == b
    if math.isnan(af) and math.isnan(bf):
        return True
    return abs(af - bf) <= max(RECON_ATOL, RECON_RTOL * max(abs(af), abs(bf)))


# --------------------------------------------------------------------------- #
# SE MODELLING (READ_RULE.md §1, §4.3 item 2)                                   #
# --------------------------------------------------------------------------- #
def se_model(n_decks: int) -> float:
    """`SE_D(model) = 14.67 / sqrt(n_decks)`. 200 decks -> 1.0374; 400 -> 0.7335."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    """§1: print realized vs modelled SE and FLAG a ratio outside [0.70, 1.43].
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
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


# --------------------------------------------------------------------------- #
# G-IDENT (READ_RULE.md §3, §3.4) — THE ONE IMPLEMENTATION                      #
#                                                                               #
# ⭐ THE ROUND-LEVEL GATE. A FAIL VOIDS ALL FOUR CELLS, because IDENT tests the  #
# plumbing every other cell depends on — CLI parse -> `_load_cand_leaf_cfg` ->   #
# `leaf_config_rs`'s conditional kwargs -> the rust leaf -> 400 games of scoring.#
# A defect that moves a ZERO-weight leaf moves every nonzero one too, and no     #
# A/B/D reading could then be attributed to the term rather than to the wiring.  #
#                                                                               #
# ⚠️ THE BAR IS STATISTICAL, NOT BIT-IDENTITY, AND THAT IS STRUCTURAL            #
# (DESIGN §3.1a). `_make_opponent` builds the opponent on `seed + 1` so the two  #
# sides never share a determinization stream; the two seatings of a deck are two #
# DIFFERENT games, not a game and its mirror, so `D(d)` carries the full         #
# per-deck variance. Confirmed empirically on a 2-deck off-band probe:           #
# `D = -11.5` and `+2.5`, byte-stable across two identical invocations.          #
# ⛔ DO NOT "fix" this by patching the offset — removing the `+1` would collapse  #
# the two seatings into one game and destroy the deck-paired estimator.          #
#                                                                               #
# ⚠️ A null bar is weak by nature: it fails by bad luck ~5% of the time when the #
# wiring is perfect. ACCEPTED DELIBERATELY — a false U-UNREADABLE costs a band   #
# and is recoverable; a true wiring defect read as a term effect is not. On a    #
# fail the readout must report the failure as AMBIGUOUS BETWEEN DEFECT AND DRAW. #
# --------------------------------------------------------------------------- #
def ident_z_ok(z: float | None) -> bool:
    """§3's statistical conjunct alone: `|z_IDENT| <= 2.0` at the cell's OWN
    realized SE. `None` (fewer than two paired decks) is FAIL — ABSENT is FAIL."""
    if z is None:
        return False
    if isinstance(z, float) and math.isnan(z):
        return False
    return abs(z) <= IDENT_ABS_Z_MAX


def ident_gate(mean, z, n_paired, *, leaf_hash_ok, n_failed, leaf_diff_empty) -> dict:
    """READ_RULE §3 `G-IDENT`, in full. **Called by BOTH the launcher's in-flight
    pre-check (DESIGN §6.4 — it refuses to start any A/B/D cell until IDENT
    passes) and the adjudicator's post-hoc gate.** One implementation, so the two
    cannot drift.

    Every conjunct is a REQUIRED keyword argument with no default: a caller that
    cannot answer one must pass the falsy/None value explicitly and see the gate
    fail closed, rather than inheriting a permissive default.

        |z| <= 2.0                       at the cell's own realized SE
        AND G-LEAF(c)                    candidate hash == champion hash
        AND n_failed == 0
        AND G-SINGLEVAR(b) empty         the leaf diff is EMPTY
    """
    z_ok = ident_z_ok(z)
    failed_ok = (n_failed == 0)
    conj = {
        "z_within_bar": z_ok,
        "leaf_hash_is_champion": bool(leaf_hash_ok),
        "n_failed_zero": bool(failed_ok),
        "leaf_diff_empty": bool(leaf_diff_empty),
    }
    ok = all(conj.values())
    return {
        "ok": ok,
        "conjuncts": conj,
        "mean": mean, "z": z, "n_paired": n_paired,
        "bar": IDENT_ABS_Z_MAX,
        "n_failed": n_failed,
        "reading": (
            "PASS — the plumbing carries a zero faithfully."
            if ok else
            "FAIL — ⚠️ AMBIGUOUS BETWEEN A WIRING DEFECT AND A DRAW FROM THE ~5% "
            "TAIL OF A NULL BAR. The readout must NOT assert a defect; the "
            "diagnosis is the leaf-hash conjunct and a re-run, not a narrative."
        ),
        "consequence": (
            "" if ok else
            "⛔ ALL FOUR CELLS ADJUDICATE U-UNREADABLE (READ_RULE §3.4). No D_C "
            "is reported as a result for any of them."
        ),
        "converse_warning": (
            "⚠️ A PASSING G-IDENT proves the plumbing carries a ZERO faithfully. "
            "It does NOT prove a nonzero weight reaches the rust leaf — that is "
            "G-INVASION's, G-CAPFWD's and G-WHEEL's job, and G-LEAF(c)'s hash "
            "asymmetry is the cheap cross-check."
        ),
    }


# --------------------------------------------------------------------------- #
# THE BRANCHES (READ_RULE.md §4) — first-match-wins, U-UNREADABLE first         #
# --------------------------------------------------------------------------- #
def branch_for_cell(z, gates_ok: bool) -> str:
    """READ_RULE §4's per-cell branch table, FIRST-MATCH-WINS, with
    `U-UNREADABLE` checked FIRST (§4's stated order of evaluation).

        U-UNREADABLE   any gate FAIL on the cell (or a round-wide G-IDENT fail,
                       which the caller folds into `gates_ok`), or no z at all
        PROMOTE        z >= +2.0
        BRACKET        +1.0 <= z < +2.0
        REVERSED       z <= -2.0
        NULL           everything else  (-2.0 < z < +1.0)

    ⚠️ The caller applies this to the THREE ARM cells only. `IDENT` is a
    PRECONDITION, not a fifth result (DESIGN §3.1); no branch fires on it.

    ⚠️ The bars are the ones READ_RULE writes: `>=`, `<=`, `<`. Exactly `+2.0`
    PROMOTES, exactly `+1.0` BRACKETS, exactly `-2.0` REVERSES. The instrument
    tests drive each endpoint for that reason.

    ⛔ The round-level `SCREEN-NULL-family-parks` is NOT a per-cell branch: it
    fires iff all gates pass on all four cells AND every arm reads `NULL` with
    `z < +1.0` AND no cell fired `REVERSED`. `round_branch()` decides it.
    """
    if not gates_ok or z is None or (isinstance(z, float) and math.isnan(z)):
        return "U-UNREADABLE"
    if z >= PROMOTE_Z:
        return "PROMOTE"
    if z >= BRACKET_Z:          # and, by the line above, z < PROMOTE_Z
        return "BRACKET"
    if z <= REVERSED_Z:
        return "REVERSED"
    return "NULL"


def round_branch(cell_branches: Mapping[str, str]) -> str:
    """READ_RULE §4's ROUND-level reading, given each cell's own branch.

        U-UNREADABLE                any cell unreadable (G-IDENT voids all four)
        SCREEN-NULL-family-parks    every arm NULL, nothing REVERSED
        MIXED                       otherwise — the per-cell branches ARE the
                                    readout; each cell is adjudicated against
                                    ZERO, on its own decks, and NEVER against a
                                    sibling (§1: no cross-cell contrast is a
                                    branch input).
    """
    arms = [cell_branches.get(c.name) for c in ARM_CELLS]
    if any(b == "U-UNREADABLE" for b in cell_branches.values()):
        return "U-UNREADABLE"
    if all(b == "NULL" for b in arms):
        return "SCREEN-NULL-family-parks"
    return "MIXED"


# --------------------------------------------------------------------------- #
# THE GUARDED ELO CONVERSION (READ_RULE.md §4.4)                                #
#                                                                               #
# Under a null `D ~ 0`, so a cell's own `elo/D` is a quotient of two             #
# independently-noisy near-zero quantities: it does not converge and its SIGN is #
# not stable. Unguarded, that ratio turns a division artifact into the printed   #
# headline elo. The rule is branch-dependent and the limb that applied is        #
# printed on every branch.                                                      #
# --------------------------------------------------------------------------- #
def elo_display(z, D, elo, se) -> dict:
    """READ_RULE §4.4's two-limb conversion.

    `|z| >= 2.0`  -> limb "own-ratio": THIS cell's realized `elo/D` is reportable
                     and the elo display goes through it, cross-checked against
                     `ELO_PER_PT_BRACKET` — a reading outside it is FLAGGED as a
                     witness anomaly and is NEVER a branch input.
    otherwise     -> limb "pinned-bracket": the cell's own ratio is NOT
                     reportable and MUST NOT be printed as a scale. The 2-sigma
                     bound is quoted as a RANGE through both pinned endpoints and
                     LABELLED a bracket conversion, not a measured scale.
    """
    lo_b, hi_b = ELO_PER_PT_BRACKET
    two_sigma_pts = (2.0 * se) if se is not None else None
    usable_z = (z is not None and not (isinstance(z, float) and math.isnan(z)))

    if usable_z and abs(z) >= PROMOTE_Z and elo is not None and D not in (None, 0, 0.0):
        epp = elo / D
        outside = not (min(lo_b, hi_b) <= abs(epp) <= max(lo_b, hi_b))
        return {
            "limb": "own-ratio",
            "label": "MEASURED SCALE — this cell's own realized elo/pt",
            "elo_per_point": epp,
            "elo_per_point_bracket": [lo_b, hi_b],
            "elo_per_point_outside_bracket": outside,
            "anomaly_note": ("⚠️ elo/pt OUTSIDE the in-family bracket "
                             f"[{lo_b}, {hi_b}] — FLAGGED as a witness anomaly, "
                             "NEVER a branch input." if outside else ""),
            "elo": elo,
            "two_sigma_pts": two_sigma_pts,
            "two_sigma_elo": (abs(epp) * two_sigma_pts) if two_sigma_pts is not None else None,
            "two_sigma_elo_lo": None, "two_sigma_elo_hi": None,
        }

    return {
        "limb": "pinned-bracket",
        "label": ("BRACKET CONVERSION, NOT A MEASURED SCALE — this cell's own "
                  "elo/D is a quotient of two noisy near-zero quantities and is "
                  "NOT reportable (READ_RULE §4.4)"),
        "elo_per_point": None,
        "elo_per_point_bracket": [lo_b, hi_b],
        "elo_per_point_outside_bracket": None,
        "anomaly_note": "",
        "elo": elo,
        "two_sigma_pts": two_sigma_pts,
        "two_sigma_elo": None,
        "two_sigma_elo_lo": (two_sigma_pts * lo_b) if two_sigma_pts is not None else None,
        "two_sigma_elo_hi": (two_sigma_pts * hi_b) if two_sigma_pts is not None else None,
    }


# --------------------------------------------------------------------------- #
# THE WHEEL PROBE CONTRACT (DESIGN.md §7, READ_RULE.md §3 G-WHEEL)              #
#                                                                               #
# ⛔ A STALE WHEEL IS THE WORST POSSIBLE FAILURE MODE FOR THIS PAIR, and the      #
# reason `leaf_config_rs` forwards the knobs CONDITIONALLY: a build predating    #
# the family serves every default-off (champion) config UNCHANGED AND SILENTLY,  #
# so a stale-wheel IDENT cell would PASS, and only a `TypeError` on the first    #
# A/B/D game would reveal it — AFTER 8 core-h. Worse, a partial mismatch would   #
# read as "the term is worth nothing" instead of "the term never ran".           #
#                                                                               #
# The launcher preflights the wheel IN A CHILD PROCESS and writes WHEEL_PROBE    #
# .json. This function is the ONE definition of what that file must contain, so  #
# the writer and the reader cannot drift.                                        #
#                                                                               #
# ⚠️ `carc_rs.__version__` is permanently "0.1.0" (workspace Cargo version; no    #
# build.rs, no vergen, no compiled-in sha) and CANNOT tell a fresh wheel from a  #
# stale one. It must NEVER be used as a build discriminator. The real            #
# fingerprint is `rust_agent.carc_rs_build_id()` plus `carc_rs_binary_sha`.      #
# --------------------------------------------------------------------------- #
WHEEL_PROBE_FILENAME = "WHEEL_PROBE.json"

#: Every key the launcher's wheel probe must write true. Each names a DIFFERENT
#: failure the stale wheel produces, and a `hasattr` proxy is deliberately not
#: enough for the middle one — DESIGN §7 requires the ACTUAL nonzero forward.
WHEEL_PROBE_REQUIRED_TRUE = (
    "invasion_terms_attr",        # carc_rs.MirrorState has `invasion_terms`
    "nonzero_kwarg_forward_ok",   # leaf_config_rs(replace(CHAMP, invasion_beta=0.12)) built
    "cap_biconditional_ok",       # DESIGN §2.3's cap-forwarding biconditional holds
)


def wheel_probe_ok(probe: Mapping | None) -> tuple[bool, str]:
    """`(ok, reason)` for a `WHEEL_PROBE.json` payload. ABSENT is FAIL."""
    if not isinstance(probe, Mapping) or not probe:
        return False, "WHEEL_PROBE.json ABSENT or empty — ABSENT is FAIL"
    missing = [k for k in WHEEL_PROBE_REQUIRED_TRUE if probe.get(k) is not True]
    if missing:
        return False, ("wheel probe did not record a successful nonzero-kwarg "
                       f"forward: {', '.join(missing)} not true")
    if not probe.get("carc_rs_build"):
        return False, "wheel probe carries no `carc_rs_build` fingerprint"
    return True, "wheel probe recorded a successful nonzero-kwarg forward"


# --------------------------------------------------------------------------- #
# SOURCE-REVISION MATCHING (READ_RULE.md §3 G-REV)                              #
#                                                                               #
# ⚠️ READ_RULE §3 says "`config.code_rev` equals the launcher's                  #
# `PINNED_SRC_REV`". Taken as string equality that proposition can NEVER hold:   #
# `carcassonne_ai.run_manifest.code_rev()` emits `git rev-parse --short HEAD`    #
# (7-12 hex, plus a `-dirty` suffix on a dirty tree) while `PINNED_SRC_REV` is   #
# written from `git rev-parse HEAD` (40 hex). "Equals" is therefore read as      #
# "NAMES THE SAME COMMIT": a case-insensitive PREFIX match of at least 7 hex.    #
#                                                                               #
# ⭐ THE `-dirty` SUFFIX IS INFORMATIONAL, NOT FATAL (amendment round 2,          #
# 2026-08-26). `code_rev()` computes dirtiness over the WHOLE TREE, and the main #
# tree is PERPETUALLY dirty with measurement logs, archives and run artifacts —  #
# that is normal and permanent, not a defect. Treating the whole-tree marker as  #
# fatal voided EVERY real cell run from the main tree, which the round-2 smoke   #
# proved (`code_rev 'dbf78ed8-dirty' marks a DIRTY tree`).                       #
#                                                                               #
# The precedent is `track_d2r4_prep`'s `G-TOOL`: whole-tree dirt is              #
# INFORMATIONAL, only CODE_PATHS dirt is fatal. This pair already carries the    #
# code-path-scoped verdict — `SRC_CLEAN.jsonl`, written by the launcher at every #
# boundary from `git status --porcelain -- src engine scripts rust tests         #
# pyproject.toml setup.py` (measurement/ DELIBERATELY excluded). `G-REV`'s       #
# dirty judgment is keyed on THAT, via `src_clean_facts`. So nothing is          #
# relaxed: the fatal check MOVED to the scope that can actually distinguish a    #
# mid-round code edit from a log file.                                          #
# --------------------------------------------------------------------------- #
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"


def split_dirty(code_rev: str) -> tuple[str, bool]:
    """`(sha_part, had_dirty_marker)`. The marker is WHOLE-TREE scoped and is
    reported, never fatal — see the banner."""
    s = (code_rev or "").strip()
    if s.lower().endswith(DIRTY_SUFFIX):
        return s[: -len(DIRTY_SUFFIX)], True
    return s, False


def rev_matches(code_rev, pinned) -> tuple[bool, str]:
    """`(ok, why)` — does a manifest's short `code_rev` NAME `PINNED_SRC_REV`?

    ⛔ This answers the IDENTITY question only. The CLEANLINESS question is
    `SRC_CLEAN.jsonl`'s (`src_clean_facts`), because only that reading is scoped
    to the code paths. A `-dirty` marker here is noted in `why` and does not
    fail the match.
    """
    if not code_rev or not isinstance(code_rev, str):
        return False, "code_rev ABSENT — ABSENT is FAIL"
    if not pinned or not isinstance(pinned, str):
        return False, "PINNED_SRC_REV ABSENT — ABSENT is FAIL"
    cr, dirty = split_dirty(code_rev)
    cr = cr.lower()
    pn = pinned.strip().lower()
    note = ("; ⚠️ whole-tree `-dirty` marker present — INFORMATIONAL ONLY "
            "(the code-path verdict is SRC_CLEAN.jsonl's)" if dirty else "")
    if not is_hex40(pn):
        return False, f"PINNED_SRC_REV {pinned!r} is not a 40-hex sha{note}"
    if len(cr) < MIN_REV_PREFIX or any(ch not in "0123456789abcdef" for ch in cr):
        return False, f"code_rev {code_rev!r} is not >= {MIN_REV_PREFIX} hex chars{note}"
    if not pn.startswith(cr):
        return False, f"code_rev {code_rev!r} is not a prefix of PINNED_SRC_REV {pinned!r}{note}"
    return True, f"code_rev {code_rev!r} names PINNED_SRC_REV {pinned!r}{note}"


def is_hex40(s) -> bool:
    return (isinstance(s, str) and len(s) == 40
            and all(c in "0123456789abcdef" for c in s.lower()))


# --------------------------------------------------------------------------- #
# THE FROZEN INPUTS AND THE POWER TABLE — §4.3 items 4, 7, 8                    #
# Mandatory readout content on EVERY branch, including U-UNREADABLE.            #
# --------------------------------------------------------------------------- #
#: DESIGN §3.2 — the derivation constants, so a reader can re-do the arithmetic
#: without opening the design. G = the champion leaf's own median sibling p90-p10
#: at the 93 Stage-A census positions; M_shape = the shape's median |T| when it
#: fires; the target is 0.40 x G. All three weights land at 40.9% of G.
FROZEN_DERIVATION = {
    "G_sibling_p90_minus_p10": 1.76,
    "target_fraction_of_G": 0.40,
    "target_contribution_pts": 0.704,
    "M_A": 6.0, "M_B": 8.0, "M_D": 6.0, "M_C": 3.03,
    "alpha_cap": 11.0,
    "stub_max_tiles": 2,
    "corroboration": ("G=1.76 (median sibling p90-p10) is independently "
                      "corroborated by the mean top1-top2 gap of 1.72, within 3%, "
                      "from a completely different definition"),
}

#: DESIGN §4.2 — computed BEFORE any answer existed. MANDATORY output on every
#: null (§4.3 item 4). ⛔ A NULL IS A BOUND, NOT A ZERO.
POWER_TABLE = (
    {"true_effect_pts": 0.72, "z_at_se_0p7335": 0.98, "power": "~16%",
     "note": "the frozen 40%-of-G target, if it transferred 1:1 to margin"},
    {"true_effect_pts": 1.47, "z_at_se_0p7335": 2.00, "power": "~52%", "note": ""},
    {"true_effect_pts": 2.06, "z_at_se_0p7335": 2.80, "power": "80%",
     "note": "the 80%-power MINIMUM DETECTABLE EFFECT (~ +-25-28 elo)"},
    {"true_effect_pts": 2.93, "z_at_se_0p7335": 4.00, "power": "~98%", "note": ""},
)

#: DESIGN §3.4 — named now, NOT RUN. ⛔ No branch may quote these as data. They
#: exist so a BRACKET or PROMOTE fires into a SPECIFIED follow-up instead of a
#: fresh argument about weights.
ROUND2_BRACKET = {
    "A": {"knob": "invasion_beta", "low": 0.04, "mid": 0.12, "high": 0.36},
    "B": {"knob": "invasion_alpha", "low": 0.03, "mid": 0.09, "high": 0.27,
          "note": "at cap 11.0"},
    "D": {"knob": "invasion_delta_farm", "low": 0.04, "mid": 0.12, "high": 0.36},
    "C": {"knob": "invasion_gamma", "low": 0.08, "mid": 0.23, "high": 0.69,
          "note": "ROUND 2 IN FULL — shape C is not run in round 1 at all "
                  "(DESIGN §3.3: C is defence-only and not antisymmetric; an "
                  "H2H-vs-champion NULL for C is EXPECTED and not disconfirming)"},
}

#: READ_RULE §4.2 — the joint A/D reading basis. MANDATORY on any A or D branch.
#: `T_A == (cities+roads part) + T_D` EXACTLY, so A_MID and D_MID are two points
#: on ONE 2-D surface, not two shapes.
AD_JOINT_BASIS = {
    "A_MID": {"beta": 0.12, "beta_plus_delta_farm": 0.12,
              "reads_as": "0.12 on cities, roads AND farms"},
    "D_MID": {"beta": 0.00, "beta_plus_delta_farm": 0.12,
              "reads_as": "0.12 on farms ONLY"},
    "readings": {
        ("A", "not D"): "the CITIES+ROADS part carries the effect; the farm part "
                        "alone is not enough",
        ("D", "not A"): "the FARM part carries it, and applying the same weight to "
                        "cities+roads CANCELS some of it — a scope finding about "
                        "where the term should apply, not two shapes",
        ("A", "D"): "ONE EFFECT OBSERVED TWICE, on disjoint decks. ⛔ NOT two "
                    "independent confirmations, NOT additive, and the two z's must "
                    "NEVER be combined, pooled, or described as 'consistent "
                    "evidence from two shapes'",
        ("neither",): "the contested-value transfer is null at this weight, on both "
                      "scopes",
    },
}

#: READ_RULE §5 — what NO branch does. Printed in full on every branch so a
#: readout cannot narrate past a limit the pair stated before game 1.
NO_BRANCH_DOES = (
    "No branch reports a production result — 2752 is the SCREENING budget, "
    "production is 11008. Screens aim, they don't verdict.",
    "No branch ranks the shapes against each other — the deck ranges are DISJOINT.",
    "No branch says anything about shape C — it is not run.",
    "No branch treats A and D as independent (§4.2).",
    "No branch generalizes from the mid weight to the family — one weight per "
    "shape; the x3 points are unrun.",
    "No branch reads a D-null as 'farms don't matter' — T_D's one-ply sibling-Δ is "
    "~0 at 94.6% of the census positions.",
    "No branch edits governance/PRODUCTION.yaml, and no firing branch adopts "
    "anything.",
    "No branch uses the ms/move ratio as evidence of anything but COST.",
    "No branch pools this band with any other (CL-068; band identity is "
    "load-bearing).",
    "No branch re-derives the weights — frozen in DESIGN §3.2, reproducible, not "
    "revisable, after the blind commit.",
)

#: READ_RULE §6 — the stated prior, recorded BEFORE game 1 so the readout can be
#: SCORED against it rather than FITTED to it. ⚠️ Priors, not bars: no branch
#: condition anywhere in §4 depends on them.
STATED_PRIOR = (
    "~55% SCREEN-NULL-family-parks (no shape reaches +1σ) · ~25% at least one "
    "shape reaches BRACKET, most likely A (largest firing rate 79.6% and largest "
    "sibling variation 1.60 on the census corpus) · ~12% some shape reaches "
    "PROMOTE · ~8% some shape reads REVERSED, concentrated on A and D via the "
    "opp_bonus_cap over-correction mechanism. D is the LEAST likely of the three "
    "to fire, on §3.2(v)'s one-ply flatness — and, symmetrically, a D reading is "
    "the LEAST informative about its own mechanism."
)


def sanity_check() -> list[str]:
    """Internal consistency of the frozen spec. Returns a list of PROBLEMS (empty
    == clean). Called by the adjudicator's `--selftest` and by the instrument
    tests, so a typo in a seed range cannot survive to launch.
    """
    problems: list[str] = []
    seen: dict[int, str] = {}
    for c in CELLS:
        if c.n_games != 2 * c.n_decks:
            problems.append(f"{c.name}: n_games {c.n_games} != 2 * n_decks {c.n_decks}")
        for s in c.seeds:
            if s in seen:
                problems.append(f"seed {s} claimed by BOTH {seen[s]} and {c.name}")
            seen[s] = c.name
        if not (BAND <= c.seed_start):
            problems.append(f"{c.name}: seed_start {c.seed_start} below the band {BAND}")
        if set(c.invasion_values) != set(c.invasion_keys):
            problems.append(f"{c.name}: invasion_values keys != invasion_keys")
        for k in c.invasion_keys:
            if k not in INVASION_DEFAULTS:
                problems.append(f"{c.name}: {k} is not an invasion field")
            elif c.invasion_values[k] == INVASION_DEFAULTS[k]:
                problems.append(f"{c.name}: {k} frozen AT its default — it would be "
                                "dropped by _leaf_dict and could never be observed")
    # the four ranges must be CONTIGUOUS as well as disjoint (DESIGN §5.1's block)
    ordered = sorted(CELLS, key=lambda c: c.seed_start)
    for a, b in zip(ordered, ordered[1:]):
        if b.seed_start != a.seed_end + 1:
            problems.append(f"gap/overlap between {a.name} and {b.name}")
    smoke = range(SMOKE_SEED_START, SMOKE_SEED_START + SMOKE_DECKS)
    for c in CELLS:
        if set(smoke) & set(c.seeds):
            problems.append(f"SMOKE range overlaps {c.name}")
    if IDENT_CELL.cand_leaf_hash != PROD_LEAF_HASH:
        problems.append("IDENT's candidate hash must EQUAL the champion hash")
    for c in ARM_CELLS:
        if c.cand_leaf_hash == PROD_LEAF_HASH:
            problems.append(f"{c.name}: a nonzero weight must MOVE the leaf hash")
    if IDENT_CELL.allow_leaf_hash_drift:
        problems.append("IDENT must NOT be launched with --allow-leaf-hash-drift")
    for c in ARM_CELLS:
        if not c.allow_leaf_hash_drift:
            problems.append(f"{c.name} MUST be launched with --allow-leaf-hash-drift")
    return problems


if __name__ == "__main__":  # pragma: no cover — a convenience for the launcher
    import json as _json
    import sys as _sys
    bad = sanity_check()
    print(_json.dumps({
        "band": BAND,
        "cells": [{"name": c.name, "seed_start": c.seed_start, "seed_end": c.seed_end,
                   "n_decks": c.n_decks, "n_games": c.n_games,
                   "out_subdir": c.out_subdir, "leaf_json": c.leaf_json,
                   "cand_leaf_hash": c.cand_leaf_hash,
                   "allow_leaf_hash_drift": c.allow_leaf_hash_drift}
                  for c in CELLS],
        "round_cost_base": project_round_cost(),
        "round_cost_plus_margin": project_round_cost(cand_margin=CAND_MARGIN_TABLE),
        "sanity_problems": bad,
    }, indent=2))
    _sys.exit(1 if bad else 0)
