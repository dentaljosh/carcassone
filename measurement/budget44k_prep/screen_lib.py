#!/usr/bin/env python3
"""`screen_lib` — THE 44032 BUDGET-RUNG ROUND's shared instrument library.

⭐ A FORK of `measurement/fpu_swap_cell_20260901/screen_lib.py`, carrying the
hardened generic parts in CONSTRUCTION (`resolve`/`gate`, `paired_margin`,
`winrate_elo`, `recon_close`, `rev_matches`/`is_hex40`, `host_matches_box`,
`se_model`, `elo_sigma_*`) and REWRITING everything round-specific.

⛔⛔ **WHAT THIS ROUND MEASURES.** The fleet wheel (flattening + follow-ons A +
the L2 solver swap) made the deployed champion ~2.2x faster — `2.433 s/move`
re-measured at the deployed `k16x1376 = 22016`, arbiter armed both seats
(`measurement/wheel_rollin_20260901/README.md`; stamped into
`governance/PRODUCTION.yaml` `deploy_profiles.desktop.measured_s_per_move`).
That speedup pays for ONE more budget doubling at roughly the OLD wall-clock:
44032 costs ~4.9 s/move against the ~5.38 s/move the program already tolerated
pre-swap. So the question "should PRODUCTION's `fair_deploy` budget flip to
44032?" is, for the first time on this ladder, NEARLY CLOCK-FREE.

The round is a DEPLOYED-vs-DEPLOYED head-to-head — the instrument class the
`fpu_h2h` / `fpu_h2h_r2` / `fpu_swap_cell` rounds battle-tested — with an
ASYMMETRIC BUDGET:

  * CANDIDATE  = the champion at total 44032, in one of TWO allocations
                 (`--k-dets` / `--sims`, the candidate-side flags);
  * OPPONENT   = the UNMODIFIED deployed champion at `k16 x 1376 = 22016`
                 (`--opp-k-dets` / `--opp-sims`, verified present in
                 `scripts/classical_search/eval_fair_puct.py`'s argparse at
                 build time);
  * BOTH SEATS carry the deployed tie-arbiter (B=64 / J=4 / argmax /
    `tiearb2-deploy-v1` / eps 0.0 / phase_gate `all`) — this is a SYMMETRIC-
    ARBITER cell, the shape `tiearb_gates.py` exists to express.

⛔ **CL-070 RIDER, cited so nobody reaches for the wrong ruler.** The RoD-v2
anchor CANNOT price budgets above 2752 (`governance/CLAIM_REGISTRY.csv`
CL-070: "RoD-v2 cannot price budget above 2752 ... so stop buying budget rungs
graded against it"). It is IRRELEVANT here — this design grades deployed
against deployed in direct head-to-head play and never touches that anchor —
but the citation is deliberate so a later reader does not "improve" the round
by re-grading it against RoD-v2.

⛔ **ABSENT IS FAIL, never a skip and never a default** — the standing
convention of every prereg pair in this tree since `phasegate_prep`.

⛔ **MOBILE IS OUT OF SCOPE.** `governance/PRODUCTION.yaml`
`deploy_profiles.mobile` runs `k16 x 1376 = 22016` on the phone and this round
licenses NOTHING about it. A desktop flip would BREAK desktop-mobile budget
parity; that consequence is named in `PREREG.md` §7 and is for the owner to
price, not for this round to propagate.
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

#: ⛔ PROPOSED, NOT CLAIMED at build time. See `BAND_CLAIMED.placeholder`.
#: `governance/BAND_REGISTRY.csv` (read 2026-09-01) ends at `172e9`
#: (`TAU_P AUDIT LEG, CELL_TAU8`, status `claimed`); `170e9`/`171e9`/`172e9`
#: are all taken, `173e9` is the next monotone-free id. The registry is
#: NECESSARY BUT NOT SUFFICIENT — the standing `146e9` trap is a band absent
#: from the registry but genuinely referenced elsewhere in the tree — so a
#: FRESH tree sweep at claim time is the binding check.
PROPOSED_BAND = 173_000_000_000

#: ⭐ ONE BAND FOR BOTH CELLS, DELIBERATELY. The screen's 400 decks are a
#: STRICT PREFIX SUBSET of the primary's 800, so the width contrast (§4.5) is a
#: WITHIN-BAND, DECK-MATCHED difference — the robust class under the CROSS-BAND
#: ~2x humility rule (CLAUDE.md; CL-068). The price is that the two cells are
#: NOT independent: a pathological deck draw moves both the same way, and one
#: band retires instead of two. Both consequences are stated in `PREREG.md`
#: §3.3 rather than left implicit.
THROWAWAY_BASE = PROPOSED_BAND + 999_000
THROWAWAY_SPAN = 1_000

#: `DESIGN` — identical on BOTH sides. Carried from `fpu_swap_cell_20260901` /
#: `fpu_h2h_r2_prep`, current at freeze time.
LEAF_HASH = "a36d2e15a3b3d71d"
EXACT_K, EXACT_MODE = 2, "marginalized"
RULES_PROFILE = "fixed_v1"
BACKEND = "rust"

#: ⭐ THE OPPONENT — `governance/PRODUCTION.yaml` `champion.fair_deploy`, the
#: 2026-08-30 promoted desktop champion (owner verbatim: "yes, desktop champ
#: becomes 22k"). UNMODIFIED. This is the incumbent the flip would replace.
OPP_K_DETS, OPP_SIMS_PER_DET, OPP_TOTAL_SIMS = 16, 1376, 22016

#: ⭐⭐ THE CANDIDATE BUDGET — one doubling above the incumbent.
CAND_TOTAL_SIMS = 44032

#: The deployed tie-arbiter spec, cited from `tiearb_gates.py` rather than
#: retyped. BOTH seats carry it in this round.
DEPLOYED_TIEARB = dict(TA.DEPLOYED_TIEARB_B64)

#: ⚠️ OWNER OVERRIDE, RECORDED: the round runs on the LOCAL box at **W = 30**
#: (owner ruling 2026-09-01, verbatim: "fund 44k at w30."). This is an explicit
#: override of the standing `W = logical threads` default (local 32) — and it
#: agrees with the settled sweep, `measurement/wsweep_local_20260831/READOUT.md`
#: ("W_LOCAL = 30", plateau; W30 == W36 within 0.31%, z 1.41).
#: ⛔ W IS THROUGHPUT-ONLY. No gate, bar or branch reads it. It is recorded and
#: checked so a smoke run at a different W is not mistaken for a tenancy-
#: comparable rehearsal (`feedback_no_agent_compute_beside_eval` quantified a
#: 1.8x/move inflation from ONE stray niced core).
W_LOCAL = 30

#: `G-SAT` — a RAIL check, not a strength bar. The symmetric-cell band: this is
#: a single-variable cell (budget), both seats otherwise identical, so a healthy
#: winrate sits near 0.5 and anything outside this is a broken run.
SAT_BAND = (0.35, 0.65)
N_COMMON_FLOOR_FRACTION = 0.80
FAILURE_RATE_VOID = 0.02

#: ⭐ THE SIZING CONSTANT — carried UNCHANGED from `fpu_resurrection_prep` /
#: `fpu_h2h_r2_prep` / `fpu_swap_cell_20260901` (all cite the tiearb2 Stage-2
#: Phase B `ARB` cell: `M +3.0700 pts/deck`, `paired_z +4.445`, `n_paired 400`).
#: ⛔ POWER ARITHMETIC ONLY — never a denominator in any branch test; every
#: branch is adjudicated at the CELL'S OWN REALIZED SE.
SIGMA_D_MODEL = 13.81
SE_ANOMALY_BAND = (0.70, 1.43)

#: `RECON` tolerance.
RECON_RTOL, RECON_ATOL = 1e-6, 1e-9
#: `G-REV`: the minimum short-rev prefix `rev_matches` will canonicalize.
MIN_REV_PREFIX = 7
DIRTY_SUFFIX = "-dirty"

PAIRING_FACTOR = 1.0 / math.sqrt(2.0)          #: ≈ 0.70711

#: The `2 sigma` convention this whole tree uses for `UB95`/`LB95` (not 1.645).
BRANCH_Z = 2.0


# =========================================================================== #
# 0.1 THE PRIORS — stated, sourced, and used for POWER ONLY                   #
# =========================================================================== #

#: The immediately preceding rung: 11008 -> 22016 (`k8x1376` -> `k16x1376`),
#: `experiments/results.csv` row
#: `h2h22016_k16x1376_vs_champ_k8x1376_n700decks_b148e9_AMENDED`
#: (2026-08-25, band 148e9, n=700 decks paired): `D = +1.2293 pts/deck`,
#: `SE 0.48784`, `z = +2.52`, `elo +14.2`, W714/D29/L657 -> branch `H-POSITIVE`.
#: Promoted 2026-08-30 (owner: "yes, desktop champ becomes 22k").
D_PREV_RUNG = 1.2293
SE_PREV_RUNG = 0.48784
N_DECKS_PREV_RUNG = 700

#: ⚠️⚠️ TWO RIDERS TRAVEL WITH `D_PREV_RUNG`, and this round must launder
#: neither away.
#:  (1) TYPE-M — that row's own note: "Type-M: below own MDE +-1.55 so magnitude
#:      inflated". The realized `+1.2293` sits BELOW the cell's own 80%-power
#:      MDE, so the SIGN is the reliable part and the MAGNITUDE is biased
#:      UPWARD.
#:  (2) PROVENANCE — the FROZEN adjudicator for that round returned
#:      `U-UNREADABLE` (two archive-independent instrument defects, G-REV /
#:      G-TIEARB). `+1.2293` is an OWNER-AUTHORIZED POST-VOID RE-READ of the
#:      same archive under amended gates, **with the diagnostic z visible
#:      before authorization** (`measurement/h2h_22016_prep/AMENDMENTS.md`).
#:      The same row also records "deploy NOT licensed (2.00x wall)" — the
#:      promotion came later, by a separate owner ruling.
#: Both riders push the same way: this anchor is softer than its point estimate
#: looks. `PREREG.md` §1.1 and §4.3 say so.
TYPE_M_MDE_PREV_RUNG = 1.55

#: The rung BEFORE that one, for context: 2752 -> 11008 was a **4x** jump, not
#: a doubling, and it moved WIDTH AND BUDGET TOGETHER. results.csv
#: `cl060_h2h_k8x1376_vs_deploy_k4x688` (band 32e9, n=400 = 200 decks x 2):
#: `+49.85 elo`, `+2.9775 pts/deck`, `paired_z 3.48`. Its fixed-width
#: decomposition `cl060_budget_k4x2752_vs_deploy_k4x688` (band 44e9, n=400)
#: isolates BUDGET at fixed k4: `+27.85 elo`, `+2.24 pts/deck`,
#: `paired_z 2.24`. ⛔ NOT a per-doubling figure — do not divide it by two and
#: call it a rung.
D_4X_RUNG_CONFOUNDED = 2.9775
D_4X_RUNG_FIXED_WIDTH = 2.24

#: ⭐⭐ THE TWO LIVE FAMILIES, AND THEY DISAGREE BY ~7x. This is the reason the
#: round is worth running at all, and the reason `BAR_M` is set where it is.
#:
#: FAMILY A — THE DECAY-**RATE** FAMILY. `docs/LEVER_INDEX.md`'s budget-headroom
#: row fits the per-doubling decay of an opponent-free statistic (CL-070's
#: budget-attributable disagreement Delta, across all five adjacent doublings):
#: `r = 0.675 +- 0.057`, 95% CI [0.573, 0.796], reproduced in the narrow-gap
#: stratum at 0.642; both fits EXCLUDE 1.0 => the sum converges. Applied to the
#: last rung's realized effect: `0.675 x 1.2293 = 0.8298` pts/deck.
#: ⚠️ HONEST ASTERISK, from that same row: the ONE adjacent ratio measured AT
#: the extrapolation point is `r4 > 1` (Delta4 0.0173 -> Delta5 0.0206) and the
#: row calls that half of the anomaly **REAL** — i.e. the rate did NOT keep
#: decaying at the top rung.
DECAY_R = 0.675
DECAY_R_SIGMA = 0.057
DECAY_R4_ADJACENT = 1.19

#: FAMILY B — THE MEASURED-**PRICE** FAMILY, and it is the CURRENT bound.
#: ⛔⛔ THE +54 ELO HEADROOM FIGURE IS **SUPERSEDED**. It rested on a price of
#: `+0.7375 pts/disagreement` measured on ONE pair. A powered re-measurement
#: (150/150 ok, 126 roots, cluster-robust) put the price at
#: `+0.0673 (se 0.2041, z +0.330; bootstrap 95% CI [-0.3300, +0.4668])`
#: => the pre-registered `price << 0.2` branch FIRED, **and POWERED, not
#: underpowered**: the memo's own point prediction (0.511) would have read
#: z = 2.5 at the realized se, and the bootstrap CI's UPPER bound sits BELOW
#: it, so "the bound stands" is EXCLUDED at ~95%.
#: THE RE-STATED BOUND, same chain with only the price replaced:
#:   `P_signal 0.591, g_next = +0.1837 pts/game, H = +0.5652 pts/game`
#:   `=> ~ +7.1 elo (sigma 22.2), honest bracket ~ [-35, +49] elo, SPANS ZERO.`
#: `H` is the WHOLE remaining tail above 11008, summed over ALL further
#: doublings. **The single 11008 -> 22016 rung then measured +1.2293 pts/deck
#: (~ +14.2 elo) on its own — larger than the entire re-stated remaining
#: bound.** That is a ~6.7x out-of-sample miss, and the LEVER_INDEX row itself
#: logs it as one of two such misses.
#: MECHANISM the row names: "the decay moved from the RATE into the PRICE …
#: above 5504 the deeper pick MOVES but does not IMPROVE."
PRICE_RESTATED_G_NEXT = 0.1837
PRICE_RESTATED_TAIL_H = 0.5652

#: ⭐ THE PLANNING PRIORS. Derived, sourced, and deliberately spanning the two
#: families' disagreement rather than splitting it.
#: A-upper: the rung simply repeats (`r4 >= 1`, the direct-measurement family).
PRIOR_NO_DECAY = D_PREV_RUNG                       # +1.2293
#: A-central: one more rung at the fitted decay RATE.
PRIOR_RATE_FAMILY = DECAY_R * D_PREV_RUNG          # +0.8298
#: A-lower: the rate family with the previous rung's Type-M rider taken
#: seriously (`D_prev - SE_prev = 0.7415`, then one rung of decay).
PRIOR_TYPEM_DISCOUNTED = DECAY_R * (D_PREV_RUNG - SE_PREV_RUNG)   # +0.5005
#: B: the measured-PRICE family's own next-rung term.
PRIOR_PRICE_FAMILY = PRICE_RESTATED_G_NEXT         # +0.1837

#: Kept as the single name the power tables and prose call "the central prior".
PRIOR_CENTRAL = PRIOR_RATE_FAMILY

#: ⛔⛔ THE WIDTH PRIOR, and it is NEGATIVE for `k > 16`.
#: `governance/CLAIM_REGISTRY.csv` CL-054 (status `Promoted`, confidence
#: `high`) swept k4/k8/k16/k32 at FIXED total budget 2752 and found an
#: INVERTED-U peaked at k4: "k32x86 -6.28 z-3.55 (significantly WORSE)",
#: "k32<k16~k8<k2<k4". CL-060 and DECISIONS 2026-07-23 both add: "Peak NOT
#: bracketed above k16 (k32+ untested; CL-054's inverted-U predicts it would
#: hurt)." **k > 16 has NEVER been measured at any budget above 2752.**
CL054_K32_AT_2752 = -6.28

#: ⚖️ THE COUNTERWEIGHT, disclosed with its own weakness. At the 22016 budget
#: on ONE band (48e9), the two allocations read
#: `curve_k16x1376_22016_vs_deploy_k4x688` **+35.58 elo** (paired_z 2.68, n=196)
#: versus `curve_k8x2752_22016_vs_deploy_k4x688` **+3.51 elo** (paired_z 0.21,
#: n=198) — i.e. at that budget the WIDER, shallower allocation out-read the
#: deeper one by ~32 elo, and `governance/PRODUCTION.yaml` calls k16x1376 "the
#: corrected allocation" and k8x2752 "the naive" one. ⚠️ BUT: each row carries
#: `sigma ~= 24.9`, so the naive difference of the two is `z ~= 0.9` — **NOT a
#: resolved contrast**. And the one FIXED-BUDGET width contrast that was
#: properly powered, CL-060's item-3 close-out at 11008 (`k4x2752` vs
#: `k8x1376`, n=800 paired, band 1.19e11), read `-19.56 +- 12.30 elo`,
#: `paired_z -1.487` -> BOUNDED NULL: "the width axis at fixed 11008 CLOSES as
#: unresolvable at affordable n; bound +/-22 elo."
#: NET READING, stated plainly: **the width axis is UNRESOLVED at every budget
#: above 2752, and the only RESOLVED measurement of it (at 2752) favours
#: NARROW.**
WIDTH_PRIOR_NOTE = (
    "width unresolved above 2752; the only resolved width measurement (CL-054 "
    "@2752) is an inverted-U peaked at k4 with k32 significantly worse; the "
    "22016-band allocation contrast favours width directionally at z~0.9 "
    "(unresolved); the powered 11008 width contrast is a bounded null."
)

#: ⭐⭐ THE BAR — decision-anchored per the owner ruling 2026-08-30 ("effect
#: size sounds right"), NEVER `2 sigma-hat` of the instrument.
#:
#: DERIVATION, in one line: **`BAR_M` is the value that DISCRIMINATES THE TWO
#: LIVE FAMILIES.** Family A (decay-RATE) predicts `+0.830` for this rung;
#: family B (measured-PRICE, the current and powered bound) predicts `+0.184`,
#: with a whole-remaining-tail of `+0.565` whose bracket spans zero. Setting
#: the bar at `+0.80` puts it AT family A's prediction and ~4.4x family B's,
#: so the branch ladder reads as a family test:
#:   `B-ADOPT`        ~ "the RATE family is right, and the flip is worth it";
#:   `B-NULL-BOUNDED` ~ "the PRICE family is right, and the ladder is DONE".
#: That is decision-anchoring in the strictest sense — the bar sits at the
#: effect size that changes what the program does next, not at a multiple of
#: the instrument's noise.
#:
#: WHY NOT the FPU chain's `+1.0`: that bar is a "should we ADD a knob"
#: burden-on-the-challenger bar, and this decision is not that shape — the
#: clock is nearly free post-wheel, so the incumbent has no cost advantage to
#: defend. Using +1.0 here would import a burden the decision does not carry,
#: and would sit ABOVE family A's own prediction — pre-registering a bar the
#: better-case prior cannot clear. `PREREG.md` §4.4 prints the read
#: distribution under BOTH bars so the choice is auditable rather than
#: asserted.
#:
#: ⚠️ RELATIONSHIP TO `2 sigma-hat`, STATED EXPLICITLY (the swap-cell
#: convention): at the primary cell's n=800 decks, `se_model(800) = 0.4883`, so
#: `2 sigma-hat = 0.977` — i.e. **`BAR_M` (0.80) sits BELOW `2 sigma-hat`**.
#: It was NOT derived from `2 sigma-hat` (see the decay derivation above); the
#: consequence is that at this n the `2 sigma` condition BINDS the ADOPT branch
#: and the BAR binds the NULL-BOUNDED branch. The bar is therefore not
#: decorative — it is exactly the thing that lets a true null DISCHARGE
#: something instead of reading UNRESOLVED forever.
BAR_M = 0.80

#: The alternative bar, computed and printed for comparison ONLY. Never used
#: by `branch_for_cell`.
BAR_M_FPU_CLASS = 1.00


# =========================================================================== #
# 0.2 THE CELLS                                                               #
# =========================================================================== #
# ⭐⭐ TWO CELLS, ONE BAND, ONE COMMON OPPONENT (the deployed k16x1376=22016).
# Both candidates spend the SAME total 44032; they differ only in HOW it is
# allocated. The primary/screen split, and WHY the primary is the k32 arm, is
# argued in `PREREG.md` §3.2 (and the declined alternatives in §3.6).

CELLS = {
    "CELL_K32": {
        "role": "PRIMARY (powered)",
        "k_dets": 32, "sims_per_det": 1376, "total_sims": 44032,
        "allocation": "double WIDTH at the deployed depth",
        "n_decks": 800, "n_games": 1600,
        "deck_offset": 0,
        "chunks": 4, "decks_per_chunk": 200,
        "why": (
            "the LADDER-PRECEDENT candidate — every promoted budget step since "
            "2752 has pinned sims_per_det at 1376 and doubled k (k4x688 -> "
            "k8x1376 -> k16x1376), so k32x1376 is what the program would deploy "
            "by DEFAULT; and it is where the standing NEGATIVE prior lives "
            "(CL-054's inverted-U, k>16 never measured above 2752), which is "
            "exactly where power belongs — a REGRESSION here is the only "
            "result in this round that can CLOSE the width ladder, and a "
            "screen at n=400 could easily leave a -1.0 regression unresolved."
        ),
    },
    "CELL_SIMS": {
        "role": "SCREEN",
        "k_dets": 16, "sims_per_det": 2752, "total_sims": 44032,
        "allocation": "double DEPTH at the deployed width",
        "n_decks": 400, "n_games": 800,
        "deck_offset": 0,
        "chunks": 2, "decks_per_chunk": 200,
        "why": (
            "the MINIMAL-CHANGE candidate — it holds the promoted, measured-good "
            "width k=16 fixed and spends the new compute on the one axis that "
            "has never been shown to turn over above 1376. It carries no "
            "standing negative prior, so a screen is the proportionate spend; "
            "if it screens strongly positive while the primary does not, that "
            "is a NAMED re-open trigger for a separately funded powered round, "
            "never an automatic action."
        ),
    },
}

#: The primary's decks are `band + 0 .. band + 799`; the screen's are
#: `band + 0 .. band + 399`, a STRICT PREFIX SUBSET. `WIDTH_CONTRAST_DECKS` is
#: the overlap the secondary width read is computed on.
WIDTH_CONTRAST_DECKS = 400

PRIMARY_CELL = "CELL_K32"
SCREEN_CELL = "CELL_SIMS"


# =========================================================================== #
# 0.3 THROUGHPUT / ETA — THROUGHPUT-ONLY, never a gate or branch input        #
# =========================================================================== #

#: Realized local throughput at the INCUMBENT config (22016 both sides, arbiter
#: ARMED both seats, rust, W=30): `162.0 g/h`
#: (`measurement/wsweep_local_20260831/READOUT.md`, the settled sweep).
G_PER_H_22016_W30 = 162.0

#: The per-move cost decomposition the 44032 extrapolation rests on, from
#: `measurement/wheel_rollin_20260901/README.md` + PRODUCTION.yaml:
#:   22016 arb-ARMED  = 2.433 s/move (governance-grade, n=3 games / 208 moves)
#:   22016 search-only = 2.179 s/move (informal, same dir)
#:   => arbiter increment ~= 0.254 s/move, and the arbiter is POST-SEARCH at
#:      the root (B=64 CRN playouts per tied arm) so it does NOT scale with the
#:      search budget.
S_PER_MOVE_22016_ARBON = 2.433
S_PER_MOVE_22016_SEARCHONLY = 2.179


def cost_ratio_44k_game() -> float:
    """The per-GAME cost multiplier of a 44032-candidate cell over the
    incumbent 22016 symmetric cell. Only the CANDIDATE's search doubles; the
    opponent and both arbiters are unchanged, and the two seats alternate, so
    the game-average move cost is the mean of the two sides'.

    ⚠️ MODEL, NOT MEASUREMENT. It assumes search cost is linear in total sims
    and that the two 44032 allocations cost the same. Neither is exactly true:
    `k32x1376` runs 2x as many determinizations per move as `k16x2752`, so it
    pays 2x the per-determinization setup AND 2x the marginalized exact-K
    endgame handoffs. `PREREG.md` §6.3 requires the ETA be RE-DERIVED from the
    round's own first completed chunk (`feedback_eta_before_launch`), and the
    launcher prints that re-derivation."""
    arb = S_PER_MOVE_22016_ARBON - S_PER_MOVE_22016_SEARCHONLY
    cand = 2.0 * S_PER_MOVE_22016_SEARCHONLY + arb
    opp = S_PER_MOVE_22016_ARBON
    return ((cand + opp) / 2.0) / S_PER_MOVE_22016_ARBON


def g_per_h_44k() -> float:
    """Planning throughput for a 44032-candidate cell at local W=30."""
    return G_PER_H_22016_W30 / cost_ratio_44k_game()


def eta_hours(n_games: int) -> float:
    return n_games / g_per_h_44k()


# =========================================================================== #
# 1. ADDRESS RESOLUTION — carried verbatim in construction                     #
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
    in BOTH seatings. `diff` is CANDIDATE minus OPPONENT in points, so `D > 0`
    means the 44032 CANDIDATE won that deck and `D < 0` means the incumbent
    22016 OPPONENT did."""
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


def paired_difference(margins_a: Mapping[int, float],
                      margins_b: Mapping[int, float]):
    """⭐ THE SECONDARY WIDTH CONTRAST (`PREREG.md` §4.5). Over the decks BOTH
    cells played, `W(d) = D_a(d) - D_b(d)`; returns
    `(mean, z, n_common, se, per_deck_list)` on the same footing as
    `paired_margin`.

    ⛔ REPORTED, NEVER LICENSING. This is a within-band, deck-matched contrast
    (the robust class), but it is a THIRD statistic on the same games and the
    round pre-registers no bar for it. It reads as a direction, not a verdict.
    """
    common = sorted(set(margins_a) & set(margins_b))
    diffs = [margins_a[d] - margins_b[d] for d in common]
    n = len(diffs)
    if n < 2:
        return None, None, n, None, diffs
    mean = math.fsum(diffs) / n
    var = math.fsum((x - mean) ** 2 for x in diffs) / (n - 1)
    se = math.sqrt(var / n)
    z = (mean / se) if se > 0 else float("nan")
    return mean, z, n, se, diffs


def elo_sigma_unpaired(wr: float, n_games: int) -> float:
    return ((400.0 / math.log(10)) * math.sqrt(wr * (1 - wr) / n_games)
            / (wr * (1 - wr)))


def elo_sigma_paired(wr: float, n_games: int) -> float:
    return elo_sigma_unpaired(wr, n_games) * PAIRING_FACTOR


def winrate_elo(records: Sequence[Mapping]) -> dict:
    """W/D/L, winrate and elo recomputed from raw records. CANDIDATE-referenced
    (`won_by_champ is True` is a win for the 44032 candidate)."""
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
    """`SIGMA_D_MODEL / sqrt(n)`. POWER ARITHMETIC ONLY."""
    return SIGMA_D_MODEL / math.sqrt(float(n_decks))


#: The two cells' planning SEs, resolved now that `se_model` exists.
SE_PRIMARY = se_model(CELLS[PRIMARY_CELL]["n_decks"])     # n=800  -> ≈0.4883
SE_SCREEN = se_model(CELLS[SCREEN_CELL]["n_decks"])       # n=400  -> ≈0.6905
SE_ELO_PRIMARY = elo_sigma_paired(0.5, CELLS[PRIMARY_CELL]["n_games"])   # ≈6.14
SE_ELO_SCREEN = elo_sigma_paired(0.5, CELLS[SCREEN_CELL]["n_games"])     # ≈8.69


def se_anomaly(realized_se: float | None, n_decks: int) -> dict:
    modelled = se_model(n_decks)
    if (realized_se is None or (isinstance(realized_se, float) and math.isnan(realized_se))
            or modelled <= 0):
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True,
                "direction": "UNAVAILABLE (None or NaN realized SE)",
                "note": "SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": not (lo <= ratio <= hi),
            "direction": ("TIGHTER than modelled" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)"
                          if ratio > hi else "inside the band"),
            "note": "DISPERSION ANOMALY — reported, never a branch input"}


def elo_se_anomaly(realized_se: float | None, n_games: int) -> dict:
    """The elo leg's version of `se_anomaly`. MODELLED = `elo_sigma_paired` at
    the null footing (`wr=0.5`); REALIZED = the same formula fed the cell's own
    observed win rate. Reported, never a branch input."""
    modelled = elo_sigma_paired(0.5, n_games)
    if (realized_se is None or (isinstance(realized_se, float) and math.isnan(realized_se))
            or modelled <= 0):
        return {"realized": realized_se, "modelled": modelled, "ratio": None,
                "band": list(SE_ANOMALY_BAND), "flagged": True,
                "direction": "UNAVAILABLE (None or NaN realized SE)",
                "note": "elo SE unavailable — ABSENT is FLAGGED, never silently OK"}
    ratio = realized_se / modelled
    lo, hi = SE_ANOMALY_BAND
    return {"realized": realized_se, "modelled": modelled, "ratio": ratio,
            "band": list(SE_ANOMALY_BAND), "flagged": not (lo <= ratio <= hi),
            "direction": ("TIGHTER than modelled" if ratio < lo else
                          "WIDER than modelled (the CONCERNING direction)"
                          if ratio > hi else "inside the band"),
            "note": "ELO-DOMAIN DISPERSION ANOMALY — reported, never a branch input"}


def _phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


# =========================================================================== #
# 4. THE BRANCH LADDER — PREREG.md §4.2, pre-registered and EXHAUSTIVE         #
# =========================================================================== #

BRANCHES = ("U-VOID-INSTRUMENT", "B-REGRESSION", "B-ADOPT", "B-NULL-BOUNDED",
            "B-UNRESOLVED")


def branch_for_cell(M, se_M, *, gates_ok: bool, bar: float = BAR_M,
                    z: float = BRANCH_Z) -> str:
    """FIRST MATCH WINS, in this EXACT order (`PREREG.md` §4.2).

    `M` = candidate(44032) minus opponent(22016), pts/deck (the harness's own
    `diff` sign, CANDIDATE minus OPPONENT). `se_M` is the cell's REALIZED
    deck-paired SE (`paired_margin`'s empirical fsum-variance figure) — never
    `SE_PRIMARY`/`SE_SCREEN`, which are planning constants used for power
    arithmetic and the dispersion-anomaly ratio only.

      U-VOID-INSTRUMENT  gates failed, or no usable statistic (`M` or `se_M`
                          absent / NaN / non-positive).
      B-REGRESSION       `M + z*se <= 0` — the 44032 candidate is CLEARLY
                          WORSE than the incumbent despite double the budget.
                          Checked FIRST so a clearly-negative cell can never
                          fall through to a bounded-null reading.
      B-ADOPT            `M - z*se > 0` AND `M >= bar` — clearly better AND
                          by at least the decision-relevant size.
      B-NULL-BOUNDED     `M + z*se < bar` — the effect is BOUNDED BELOW the
                          decision-relevant size. A real, discharging read:
                          "the doubling does not buy the bar."
      B-UNRESOLVED       otherwise.

    ⚠️ WHY ADOPT IS `(LB95 > 0) AND (point >= bar)` AND NOT `LB95 >= bar`.
    The FPU chain used `LB95 >= +1.0` because that decision put the burden on a
    challenger knob against a zero-cost incumbent. HERE the incumbent has no
    cost advantage to defend — 44032 is ~4.9 s/move against the ~5.38 the
    program already tolerated pre-wheel — so requiring the candidate be proven
    better BY AT LEAST the bar would import a burden the decision does not
    carry. The test used is strictly weaker than `LB95 >= bar` and strictly
    stronger than a bare `z >= 2` (which is what the 11008->22016 round used,
    and which the owner's 2026-08-30 bar ruling now forbids as a bar
    DEFINITION). `PREREG.md` §4.4 prints the read distribution under both
    forms.

    ⛔ MUTUAL EXCLUSIVITY. `B-ADOPT` needs `M >= max(z*se, bar) > 0`;
    `B-NULL-BOUNDED` needs `M < bar - z*se < bar`; `B-REGRESSION` needs
    `M <= -z*se < 0`. REGRESSION implies the NULL-BOUNDED inequality too, which
    is exactly why REGRESSION is checked first — `sanity_check` sweeps a grid
    to prove the ladder is total and the order is the registered one.
    """
    if not gates_ok:
        return "U-VOID-INSTRUMENT"
    if (M is None or se_M is None
            or (isinstance(se_M, float) and math.isnan(se_M)) or se_M <= 0):
        return "U-VOID-INSTRUMENT"
    if (M + z * se_M) <= 0.0:
        return "B-REGRESSION"
    if (M - z * se_M) > 0.0 and M >= bar:
        return "B-ADOPT"
    if (M + z * se_M) < bar:
        return "B-NULL-BOUNDED"
    return "B-UNRESOLVED"


def power_cell(delta: float, se: float, bar: float = BAR_M,
               z: float = BRANCH_Z) -> dict:
    """The four branches' probabilities at a true advantage `delta` and SE `se`.

    Closed-form under the normal approximation, using the SAME inequalities
    `branch_for_cell` uses, with `se_hat` fixed at `se` (i.e. it prices the
    point estimate's sampling distribution and treats the realized SE as
    exactly the modelled one — the standard planning simplification, and it is
    named here rather than hidden).

    ⚠️ Reported HONESTLY (`feedback_verify_numbers_before_reporting` /
    `feedback_noisy_plateau_not_a_conclusion`): `PREREG.md` §4.3-4.4 print this
    table and do not round it up."""
    if se is None or se <= 0:
        return {k: float("nan") for k in
                ("p_adopt", "p_regression", "p_null_bounded", "p_unresolved")}
    adopt_thresh = max(z * se, bar)
    p_adopt = 1.0 - _phi((adopt_thresh - delta) / se)
    p_regression = _phi((-z * se - delta) / se)
    p_below_bar_bound = _phi((bar - z * se - delta) / se)
    p_null_bounded = max(0.0, p_below_bar_bound - p_regression)
    p_unresolved = max(0.0, 1.0 - p_adopt - p_regression - p_null_bounded)
    return {"p_adopt": p_adopt, "p_regression": p_regression,
            "p_null_bounded": p_null_bounded, "p_unresolved": p_unresolved,
            "adopt_threshold_pts_per_deck": adopt_thresh,
            "null_bounded_threshold_pts_per_deck": bar - z * se,
            "regression_threshold_pts_per_deck": -z * se,
            "binding_adopt_condition": ("the 2-sigma condition binds"
                                        if z * se >= bar else "the BAR binds")}


def mde(se: float, power: float = 0.80, bar: float = BAR_M,
        z: float = BRANCH_Z) -> float:
    """The MINIMUM DETECTABLE EFFECT at `power` for the `B-ADOPT` branch: the
    true `delta` at which `P(M_hat >= max(z*se, bar)) == power`.

    ⚠️⚠️ THIS IS THE TYPE-M TRIPWIRE, and it is why it lives in the library
    rather than in prose. `mde(SE_PRIMARY) ~= 1.39 pts/deck`, which is ABOVE
    every one of this round's own planning priors (`no-decay 1.229`,
    `central 0.830`, `Type-M-discounted 0.500`). So if this round DOES read
    `B-ADOPT`, its realized effect will very likely sit below its own MDE — the
    exact condition that made the 11008->22016 row carry a Type-M rider. The
    sign will be the reliable part; the magnitude will be biased UPWARD, and
    the readout must say so rather than propagate the number as calibrated."""
    # P(M_hat >= thr) = power  <=>  (thr - delta)/se = Phi^-1(1 - power)
    thresh = max(z * se, bar)
    # Phi^-1 by bisection on _phi (matched pair; no scipy)
    lo, hi = -9.0, 9.0
    target = 1.0 - power
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if _phi(mid) < target:
            lo = mid
        else:
            hi = mid
    q = (lo + hi) / 2.0
    return thresh - q * se


#: The priors `PREREG.md` §4.3 tabulates, in one place so the doc, the
#: adjudicator and the tests all read the same list.
POWER_PRIORS = (
    ("A-upper: no decay (r4>=1, the rung repeats)", PRIOR_NO_DECAY),
    ("A-central: decay RATE family (r x D_prev)", PRIOR_RATE_FAMILY),
    ("A-lower: rate family, Type-M discounted", PRIOR_TYPEM_DISCOUNTED),
    ("B: measured-PRICE family (g_next, the CURRENT bound)", PRIOR_PRICE_FAMILY),
    ("exact null", 0.0),
    ("mild regression (-1.0)", -1.0),
    ("CL-054-scale width regression (-3.0)", -3.0),
)


# =========================================================================== #
# 5. RIDERS                                                                    #
# =========================================================================== #

RIDERS_ALWAYS = (
    "⛔ SELF-ANCHORED: every statistic here is THIS candidate/opponent pair on "
    "THIS band, not absolute strength. No prior or later round is pooled.",
    "⛔ THIS ROUND MAKES NO SOURCE CHANGE AND CHANGES NO GOVERNANCE FILE ON "
    "ANY BRANCH. `B-ADOPT` licenses exactly two things: (1) PROPOSING a "
    "`governance/PRODUCTION.yaml` `champion.fair_deploy` budget flip to 44032 "
    "at the adopting allocation, for a separate OWNER RULING, and (2) funding "
    "an out-of-family external Carcasum corroboration step. Neither is "
    "automatic (`feedback_evloss_grader`'s F4 lesson: judge-free game outcomes "
    "outrank any single-family number, and a promotion of this size should "
    "carry an independent-engine cross-check the way the arbiter fold did).",
    "⛔ MOBILE / PHONE BUDGET IS OUT OF SCOPE ON EVERY BRANCH. "
    "`deploy_profiles.mobile` stays k16x1376=22016. A desktop flip would BREAK "
    "desktop-mobile budget parity and open a new E4 archive epoch; that is a "
    "consequence to PRICE in the flip proposal, never a change this round "
    "propagates.",
    "⛔ CL-070: the RoD-v2 anchor CANNOT price budgets above 2752. It is not "
    "used here (this is deployed-vs-deployed direct play) and must not be "
    "reached for when re-reading this round.",
    "⚠️ TYPE-M TRAVELS. The `+1.2293` prior from the 11008->22016 rung sits "
    "BELOW that cell's own 80%-power MDE (+/-1.55), so its magnitude is biased "
    "UPWARD. Any effect measured here that lands near its own MDE inherits the "
    "same caveat and must be reported with it, not propagated as calibrated.",
    "⚠️ THE TWO CELLS SHARE ONE BAND AND THE SCREEN'S DECKS ARE A SUBSET OF "
    "THE PRIMARY'S. They are NOT independent replications: a pathological deck "
    "draw moves both the same way. This is deliberate (it makes the §4.5 width "
    "contrast a within-band deck-matched read, the robust class), and it is "
    "the reason no cross-cell pooling of any kind is permitted.",
)

RIDERS_BY_BRANCH = {
    "B-ADOPT": (
        "Report WHICH cell adopted and at WHICH allocation — `CELL_K32` "
        "(k32x1376) and `CELL_SIMS` (k16x2752) are DIFFERENT production "
        "configs and an adopt of one licenses proposing only that one.",
        "⚠️ CHECK THE ELO CO-READ'S SIGN before writing the proposal. The elo "
        "leg is reported, not a branch input, but a margin-ADOPT alongside a "
        "negative elo point estimate is an incoherent read and must be hand-"
        "reviewed (RECON, G-SAT, the dispersion anomalies on both legs) before "
        "any flip is proposed.",
        "⚠️ Compare the realized effect to this cell's own MDE. If it lands "
        "below it, the Type-M rider attaches to THIS number too.",
    ),
    "B-REGRESSION": (
        "⭐ THIS IS THE HIGH-VALUE READ OF THE ROUND if it fires on "
        "`CELL_K32`: a 44032 candidate that is CLEARLY WORSE than the 22016 "
        "incumbent despite double the budget CONFIRMS CL-054's inverted-U "
        "biting above k16, CLOSES the 'keep doubling k' allocation rule, and "
        "retroactively re-frames the k8->k16 step as near the top of the "
        "curve. Say all three, and update `docs/LEVER_INDEX.md`'s budget-"
        "headroom row and CL-054/CL-060 in the same sitting.",
        "⚠️ If it fires on `CELL_SIMS` instead, the finding is about DEPTH, "
        "not width, and is much more surprising — hand-review RECON and "
        "G-BUDGET before trusting it, because 'more sims per determinization "
        "made it worse' has no standing prior at all.",
    ),
    "B-NULL-BOUNDED": (
        "⭐ A DISCHARGING READ, not a failure. It says the doubling does not "
        "buy the decision-relevant `+0.80 pts/deck`, i.e. the budget ladder "
        "has decayed below its own fitted model (`r = 0.675 +- 0.057`) at the "
        "first rung the wheel made affordable. The action is to STOP BUYING "
        "BUDGET RUNGS and record the bound — not to fund more n.",
        "Report the realized upper bound `M + 2*se` explicitly; it is the "
        "number the next reader needs.",
    ),
    "B-UNRESOLVED": (
        "⚠️ AT THE PRIMARY'S n=800 DECKS A TRUE NULL READS UNRESOLVED ROUGHLY "
        "60% OF THE TIME — this is stated up front in `PREREG.md` §4.4, not "
        "discovered afterwards. An UNRESOLVED read is therefore only weak "
        "evidence about the world; it is mostly evidence about the affordable "
        "n. Do NOT read it as 'the doubling does nothing'.",
        "An extension to larger n is a NAMED, SEPARATELY FUNDED re-open (the "
        "`fpu_h2h` -> `fpu_h2h_r2` posture), never an automatic continuation "
        "of this round. Adding n after seeing this round's numbers and re-"
        "reading at the same bars is peeking; a re-open is a fresh round with "
        "its own band and its own freeze.",
    ),
    "U-VOID-INSTRUMENT": (
        "⛔ The instrument, not the world. The statistics in the readout are a "
        "COMPANION TABLE only; no reading is taken on any axis.",
    ),
}


# =========================================================================== #
# 6. THE GATES THAT ARE THIS ROUND'S REASON FOR EXISTING                      #
# =========================================================================== #

def tiearb_sides_gate(manifest: Mapping) -> dict:
    """`G-TIEARB-SIDES` — BOTH seats ARMED at the deployed B=64 spec. A thin
    wrapper over `tiearb_gates.check_tiearb_sides` so this pair and the module
    it cites cannot drift apart. This is the SYMMETRIC-ARBITER shape: the
    budget is the only variable, so an arbiter present on one seat only would
    confound the whole round."""
    ok, findings = TA.check_tiearb_sides(manifest, cand_expected=DEPLOYED_TIEARB,
                                         opp_expected=DEPLOYED_TIEARB)
    return gate("G-TIEARB-SIDES", ok, {"findings": findings},
                "manifest cand_tiearb / opp_tiearb (see tiearb_gates.py)",
                ("BOTH seats ARMED at the deployed B=64 spec — the budget is "
                 "the only variable" if ok else
                 "⛔ G-TIEARB-SIDES FAILED: " + "; ".join(findings)))


def tiearb_fired_gate(summary: Mapping) -> dict:
    """`G-TIEARB-FIRED` — the BOTH-ARMED POSITIVE CONTROLS. The config gate
    proves the arbiter was REQUESTED on each seat; this proves it BOUND AND
    BIT on each seat (`tiearb_gates.tiearb_sides_summary`'s realized counters),
    not merely that two healthy-looking dicts were written.

    ⛔ BOTH sides must show a nonzero `fired_plies`. A cell where only one seat
    ever arbitrated is a ONE-SIDED cell wearing a symmetric cell's name — and
    since the arbiter is worth ~+66 elo on its own (the `tiearb_widening` B64
    row), a one-sided arbiter would swamp the budget effect this round is
    trying to measure."""
    sides = TA.tiearb_sides_summary(summary or {})
    bad = []
    for side in ("candidate", "opponent"):
        s = sides.get(side)
        if s is None:
            bad.append(f"{side}: `{'' if side == 'candidate' else 'opp_'}"
                       f"tiearb_games` ABSENT/zero — that seat's arbiter "
                       f"container was never exercised in PLAY, config gate "
                       f"notwithstanding")
        elif not s.get("fired_plies"):
            bad.append(f"{side}: fired_plies is {s.get('fired_plies')!r} — "
                       f"requested but never actually fired on a single tied ply")
    ok = not bad
    return gate("G-TIEARB-FIRED", ok, {k: sides.get(k) for k in
                                       ("candidate", "opponent")},
                "summary.json tiearb_* / opp_tiearb_* (tiearb_sides_summary)",
                ("BOTH seats' arbiters fired on a nonzero count of tied plies "
                 "— the both-armed positive control" if ok else
                 "⛔ G-TIEARB-FIRED FAILED: " + "; ".join(bad)))


def _budget_triple(docs, side: str):
    """`(k, sims, total, address)` for one side, from the manifest."""
    if side == "candidate":
        aliases_k = ("manifest:config.champion.k_dets",)
        aliases_s = ("manifest:config.champion.sims_per_det",)
        aliases_t = ("manifest:config.champion.total_sims",)
    else:
        aliases_k = ("manifest:config.opponent.k_dets",
                     "manifest:config.opponent.champ_cfg.k_dets")
        aliases_s = ("manifest:config.opponent.sims_per_det",
                     "manifest:config.opponent.champ_cfg.sims_per_det")
        aliases_t = ("manifest:config.opponent.total_sims",
                     "manifest:config.opponent.champ_cfg.total_sims")
    k, ka = resolve(docs, *aliases_k)
    s, _ = resolve(docs, *aliases_s)
    t, _ = resolve(docs, *aliases_t)
    return k, s, t, ka


def budget_gate(manifest: Mapping, summary: Mapping, cell_name: str) -> dict:
    """⭐⭐ `G-BUDGET` — THE GATE THIS ROUND EXISTS FOR. The CANDIDATE side's
    `k_dets x sims_per_det` must resolve to **44032** at this cell's frozen
    allocation, and the OPPONENT side's to **22016** at `k16 x 1376`, READ FROM
    THE EMITTED MANIFEST — never from the launcher's intent, never from the
    dirname.

    A SECOND, INDEPENDENT WITNESS is required: `summary.json`'s own
    `asymmetric_budgets` block (`candidate_k_dets` / `candidate_sims` /
    `candidate_total_sims` / `opp_k_dets` / `opp_sims` / `opp_total_sims`),
    which the harness writes from the RESOLVED agents at close-out. Manifest
    and summary must AGREE. A cell where the two disagree has an
    unreconstructable budget and is voided, not adjudicated.

    ⛔ The failure mode this exists to catch is silent and total: omit
    `--opp-k-dets`/`--opp-sims` and the harness runs the opponent at the SHARED
    `--k-dets`/`--sims`, i.e. a SYMMETRIC 44032-vs-44032 cell that measures
    nothing and looks perfectly healthy from the outside."""
    spec = CELLS[cell_name]
    docs = {"manifest": manifest or {}, "summary": summary or {}}
    rows, bad = {}, []

    want = {"candidate": (spec["k_dets"], spec["sims_per_det"], spec["total_sims"]),
            "opponent": (OPP_K_DETS, OPP_SIMS_PER_DET, OPP_TOTAL_SIMS)}
    addr0 = None
    for side in ("candidate", "opponent"):
        k, s, t, a = _budget_triple(docs, side)
        addr0 = addr0 or a
        rows[side] = {"k_dets": None if k is MISSING else k,
                      "sims_per_det": None if s is MISSING else s,
                      "total_sims": None if t is MISSING else t,
                      "expected": list(want[side])}
        if MISSING in (k, s, t):
            bad.append(f"{side}: a budget field is ABSENT — ABSENT is FAIL")
            continue
        if (int(k), int(s), int(t)) != want[side]:
            bad.append(f"{side}: ({k},{s},{t}) != {want[side]}")
        if int(k) * int(s) != int(t):
            bad.append(f"{side}: {k} x {s} != {t} (the manifest is internally "
                       f"inconsistent)")

    # --- the SECOND witness: summary.json's asymmetric_budgets block --------
    asym, asym_a = resolve(docs, "summary:asymmetric_budgets")
    if asym is MISSING:
        bad.append("summary.asymmetric_budgets ABSENT — the harness did not "
                   "record an asymmetric-budget cell, so either --opp-k-dets/"
                   "--opp-sims were never passed or this summary predates the "
                   "block. ABSENT is FAIL.")
    elif asym is not True:
        bad.append(f"summary.asymmetric_budgets is {asym!r}, not True — the "
                   "harness resolved the two seats to the SAME budget, which "
                   "is the exact silent failure this gate exists to catch")
    summary_rows = {}
    for side, keys in (("candidate", ("candidate_k_dets", "candidate_sims",
                                      "candidate_total_sims")),
                       ("opponent", ("opp_k_dets", "opp_sims",
                                     "opp_total_sims"))):
        vals = []
        for key in keys:
            v, _ = resolve(docs, f"summary:{key}")
            vals.append(None if v is MISSING else v)
        summary_rows[side] = dict(zip(keys, vals))
        if any(v is None for v in vals):
            bad.append(f"{side}: summary's {keys} — a field is ABSENT")
            continue
        if tuple(int(v) for v in vals) != want[side]:
            bad.append(f"{side}: summary says {tuple(vals)} != {want[side]}")
        if rows[side]["total_sims"] is not None and int(vals[2]) != int(rows[side]["total_sims"]):
            bad.append(f"{side}: manifest total_sims {rows[side]['total_sims']} "
                       f"DISAGREES with summary total_sims {vals[2]} — the "
                       "budget is unreconstructable")
    rows["summary_witness"] = summary_rows
    rows["asymmetric_budgets"] = None if asym is MISSING else asym

    return gate("G-BUDGET", not bad, rows, asym_a or addr0,
                (f"{cell_name}: candidate k{spec['k_dets']} x "
                 f"{spec['sims_per_det']} = {spec['total_sims']}, opponent "
                 f"k{OPP_K_DETS} x {OPP_SIMS_PER_DET} = {OPP_TOTAL_SIMS}, "
                 "manifest and summary agreeing" if not bad else
                 "⛔ G-BUDGET FAILED: " + "; ".join(bad)))


def budget_ratio_gate(manifest: Mapping, summary: Mapping, cell_name: str) -> dict:
    """`G-BUDGET-RATIO` — the STRUCTURAL claim, independent of magnitude:
    the candidate spends exactly **2x** the opponent's total, and spends it in
    THIS cell's registered ALLOCATION SHAPE (`CELL_K32`: same depth, double
    width; `CELL_SIMS`: same width, double depth).

    ⭐ WHY IT IS SEPARATE FROM `G-BUDGET`. `G-BUDGET` pins the exact frozen
    magnitudes and therefore cannot pass on a reduced-budget verification
    fixture. This gate states the same operator-error protection in a
    magnitude-free form, so it CAN be asserted on a tiny real-emitter fixture
    and on the launcher's `--smoke` — which is where the flag-wiring error it
    catches would actually be introduced."""
    spec = CELLS[cell_name]
    docs = {"manifest": manifest or {}, "summary": summary or {}}
    ck, cs, ct, _ = _budget_triple(docs, "candidate")
    ok_, os_, ot, addr = _budget_triple(docs, "opponent")
    bad = []
    if MISSING in (ck, cs, ct, ok_, os_, ot):
        bad.append("a budget field is ABSENT on one of the two sides — "
                   "ABSENT is FAIL")
    else:
        ck, cs, ct = int(ck), int(cs), int(ct)
        ok_, os_, ot = int(ok_), int(os_), int(ot)
        if ck * cs != ct:
            bad.append(f"candidate {ck} x {cs} != {ct}")
        if ok_ * os_ != ot:
            bad.append(f"opponent {ok_} x {os_} != {ot}")
        if ct != 2 * ot:
            bad.append(f"candidate total {ct} != 2 x opponent total {ot} — "
                       "this is not a budget DOUBLING cell")
        if cell_name == "CELL_K32":
            if ck != 2 * ok_:
                bad.append(f"CELL_K32 wants DOUBLE WIDTH: k_dets {ck} != 2 x {ok_}")
            if cs != os_:
                bad.append(f"CELL_K32 wants the DEPLOYED DEPTH: sims_per_det "
                           f"{cs} != {os_}")
        elif cell_name == "CELL_SIMS":
            if ck != ok_:
                bad.append(f"CELL_SIMS wants the DEPLOYED WIDTH: k_dets "
                           f"{ck} != {ok_}")
            if cs != 2 * os_:
                bad.append(f"CELL_SIMS wants DOUBLE DEPTH: sims_per_det "
                           f"{cs} != 2 x {os_}")
        else:                                                    # pragma: no cover
            bad.append(f"unknown cell {cell_name!r}")
    return gate("G-BUDGET-RATIO", not bad,
                {"candidate": [None if v is MISSING else v for v in (ck, cs, ct)],
                 "opponent": [None if v is MISSING else v for v in (ok_, os_, ot)],
                 "cell": cell_name, "shape": spec["allocation"]},
                addr,
                (f"{cell_name}: candidate total is exactly 2x the opponent's, "
                 f"allocated as '{spec['allocation']}'" if not bad else
                 "⛔ G-BUDGET-RATIO FAILED: " + "; ".join(bad)))


# =========================================================================== #
# 7. SELF-CHECK — the library's own invariants                                #
# =========================================================================== #

def sanity_check() -> list[str]:
    """Problems with THIS FILE's own constants and arithmetic. Empty == clean."""
    p: list[str] = []

    # --- constants ---------------------------------------------------------
    if OPP_K_DETS * OPP_SIMS_PER_DET != OPP_TOTAL_SIMS:
        p.append(f"{OPP_K_DETS} x {OPP_SIMS_PER_DET} != {OPP_TOTAL_SIMS}")
    if CAND_TOTAL_SIMS != 2 * OPP_TOTAL_SIMS:
        p.append(f"CAND_TOTAL_SIMS {CAND_TOTAL_SIMS} is not 2 x "
                 f"OPP_TOTAL_SIMS {OPP_TOTAL_SIMS}")
    if DEPLOYED_TIEARB != TA.DEPLOYED_TIEARB_B64:
        p.append("DEPLOYED_TIEARB has drifted from tiearb_gates.DEPLOYED_TIEARB_B64")
    if not (0.0 < BAR_M < 5.0):
        p.append(f"BAR_M {BAR_M} is outside a sane range")
    if PRIMARY_CELL not in CELLS or SCREEN_CELL not in CELLS:
        p.append("PRIMARY_CELL/SCREEN_CELL do not name entries in CELLS")
    if CELLS[PRIMARY_CELL]["n_decks"] <= CELLS[SCREEN_CELL]["n_decks"]:
        p.append("the PRIMARY cell is not larger than the SCREEN cell")

    for name, spec in CELLS.items():
        if spec["k_dets"] * spec["sims_per_det"] != spec["total_sims"]:
            p.append(f"{name}: {spec['k_dets']} x {spec['sims_per_det']} != "
                     f"{spec['total_sims']}")
        if spec["total_sims"] != CAND_TOTAL_SIMS:
            p.append(f"{name}: total {spec['total_sims']} != {CAND_TOTAL_SIMS}")
        if spec["n_games"] != 2 * spec["n_decks"]:
            p.append(f"{name}: n_games {spec['n_games']} != 2 x n_decks "
                     f"{spec['n_decks']} (the harness's --paired contract)")
        if spec["chunks"] * spec["decks_per_chunk"] != spec["n_decks"]:
            p.append(f"{name}: {spec['chunks']} chunks x "
                     f"{spec['decks_per_chunk']} decks != {spec['n_decks']}")
        if spec["deck_offset"] != 0:
            p.append(f"{name}: deck_offset {spec['deck_offset']} — the width "
                     "contrast requires the screen be a PREFIX subset")
    if WIDTH_CONTRAST_DECKS != min(s["n_decks"] for s in CELLS.values()):
        p.append("WIDTH_CONTRAST_DECKS is not the smaller cell's deck count")
    if CELLS[SCREEN_CELL]["n_decks"] > CELLS[PRIMARY_CELL]["n_decks"]:
        p.append("the screen's decks are not a subset of the primary's")

    # --- the allocation shapes really are the two named ones ---------------
    if CELLS["CELL_K32"]["k_dets"] != 2 * OPP_K_DETS:
        p.append("CELL_K32 is not a width doubling")
    if CELLS["CELL_K32"]["sims_per_det"] != OPP_SIMS_PER_DET:
        p.append("CELL_K32 does not hold the deployed depth")
    if CELLS["CELL_SIMS"]["k_dets"] != OPP_K_DETS:
        p.append("CELL_SIMS does not hold the deployed width")
    if CELLS["CELL_SIMS"]["sims_per_det"] != 2 * OPP_SIMS_PER_DET:
        p.append("CELL_SIMS is not a depth doubling")

    # --- planning SEs ------------------------------------------------------
    if abs(SE_PRIMARY - se_model(CELLS[PRIMARY_CELL]["n_decks"])) > 1e-12:
        p.append("SE_PRIMARY disagrees with se_model(primary n_decks)")
    if abs(SE_SCREEN - se_model(CELLS[SCREEN_CELL]["n_decks"])) > 1e-12:
        p.append("SE_SCREEN disagrees with se_model(screen n_decks)")
    if not (SE_PRIMARY < SE_SCREEN):
        p.append("the primary's planning SE is not tighter than the screen's")
    if abs(SE_ELO_PRIMARY - elo_sigma_paired(0.5, 1600)) > 1e-12:
        p.append("SE_ELO_PRIMARY disagrees with elo_sigma_paired(0.5, 1600)")

    # --- the priors are derived, not typed ---------------------------------
    if abs(PRIOR_RATE_FAMILY - DECAY_R * D_PREV_RUNG) > 1e-12:
        p.append("PRIOR_RATE_FAMILY is not r x D_prev")
    if PRIOR_CENTRAL is not PRIOR_RATE_FAMILY and PRIOR_CENTRAL != PRIOR_RATE_FAMILY:
        p.append("PRIOR_CENTRAL has drifted from PRIOR_RATE_FAMILY")
    if abs(PRIOR_PRICE_FAMILY - PRICE_RESTATED_G_NEXT) > 1e-12:
        p.append("PRIOR_PRICE_FAMILY is not the restated bound's g_next")
    if not (PRIOR_PRICE_FAMILY < PRIOR_TYPEM_DISCOUNTED < PRIOR_RATE_FAMILY
            < PRIOR_NO_DECAY):
        p.append("the four priors are not ordered price < typeM < rate < "
                 "no-decay — check the derivations")
    # the two families really do disagree by the ~7x the design is built around
    if not (4.0 < PRIOR_RATE_FAMILY / PRIOR_PRICE_FAMILY < 6.0):
        p.append(f"the rate/price family ratio "
                 f"{PRIOR_RATE_FAMILY / PRIOR_PRICE_FAMILY:.2f} is no longer "
                 "the ~4.5x BAR_M was set to discriminate — re-derive the bar")
    if abs(BAR_M - 0.80) > 1e-12:
        p.append("BAR_M moved without its derivation being updated")
    # ⭐ THE BAR'S OWN DERIVATION, asserted mechanically: it must sit AT the
    # rate family's prediction and WELL ABOVE the price family's.
    if not (abs(BAR_M - PRIOR_RATE_FAMILY) < 0.10):
        p.append(f"BAR_M {BAR_M} is no longer at the rate family's prediction "
                 f"{PRIOR_RATE_FAMILY:.4f} — its derivation is stale")
    if not (BAR_M > 3.0 * PRIOR_PRICE_FAMILY):
        p.append(f"BAR_M {BAR_M} no longer discriminates the price family's "
                 f"{PRIOR_PRICE_FAMILY:.4f} — the ladder stops being a family "
                 "test")
    if not (BAR_M < BRANCH_Z * SE_PRIMARY):
        p.append("BAR_M is no longer BELOW 2*SE_PRIMARY — the docstring's "
                 "'the 2-sigma condition binds ADOPT' claim is stale")

    # --- ETA model ---------------------------------------------------------
    cr = cost_ratio_44k_game()
    if not (1.30 < cr < 1.60):
        p.append(f"cost_ratio_44k_game() {cr} is outside the ~1.45 the "
                 "per-move decomposition implies — check the s/move constants")
    if not (90.0 < g_per_h_44k() < 130.0):
        p.append(f"g_per_h_44k() {g_per_h_44k()} is outside a sane range")

    # --- branch ladder: totality, order and exclusivity, swept on a grid ----
    for m100 in range(-500, 501, 5):
        M = m100 / 100.0
        for se100 in (10, 25, 35, 49, 69, 100, 150):
            se = se100 / 100.0
            b = branch_for_cell(M, se, gates_ok=True)
            if b not in BRANCHES:
                p.append(f"branch_for_cell({M},{se}) returned unknown {b!r}")
                continue
            # independent closed-form re-derivation — a witness, not a copy
            reg = (M + BRANCH_Z * se) <= 0.0
            adopt = (M - BRANCH_Z * se) > 0.0 and M >= BAR_M
            nullb = (M + BRANCH_Z * se) < BAR_M
            expect = ("B-REGRESSION" if reg else "B-ADOPT" if adopt
                      else "B-NULL-BOUNDED" if nullb else "B-UNRESOLVED")
            if b != expect:
                p.append(f"branch_for_cell({M},{se}) = {b}, independent "
                         f"re-derivation says {expect}")
            if reg and adopt:
                p.append(f"REGRESSION and ADOPT both eligible at ({M},{se}) — "
                         "the ladder is not mutually exclusive")
            if adopt and nullb:
                p.append(f"ADOPT and NULL-BOUNDED both eligible at ({M},{se})")

    # --- each branch is REACHABLE ------------------------------------------
    reached = {branch_for_cell(M, se, gates_ok=True)
               for M, se in ((-5.0, 0.49), (2.0, 0.49), (0.0, 0.10),
                             (0.9, 0.49))}
    for b in ("B-REGRESSION", "B-ADOPT", "B-NULL-BOUNDED", "B-UNRESOLVED"):
        if b not in reached:
            p.append(f"branch {b} was not reachable from the probe points "
                     f"(reached {sorted(reached)})")

    # --- void conditions ---------------------------------------------------
    if branch_for_cell(1.5, 0.4, gates_ok=False) != "U-VOID-INSTRUMENT":
        p.append("gates_ok=False did not force U-VOID-INSTRUMENT")
    for args in ((None, 0.4), (1.0, None), (1.0, float("nan")), (1.0, 0.0),
                 (1.0, -0.1), (None, None)):
        if branch_for_cell(*args, gates_ok=True) != "U-VOID-INSTRUMENT":
            p.append(f"unusable statistic {args} did not force U-VOID-INSTRUMENT")

    # --- power arithmetic --------------------------------------------------
    for se in (SE_PRIMARY, SE_SCREEN):
        for _label, delta in POWER_PRIORS:
            pw = power_cell(delta, se)
            tot = (pw["p_adopt"] + pw["p_regression"] + pw["p_null_bounded"]
                   + pw["p_unresolved"])
            if abs(tot - 1.0) > 1e-9:
                p.append(f"power_cell({delta},{se}) probabilities sum to {tot}")
            for k in ("p_adopt", "p_regression", "p_null_bounded",
                      "p_unresolved"):
                if not (0.0 <= pw[k] <= 1.0):
                    p.append(f"power_cell({delta},{se})[{k}] out of range")
    # monotone in delta
    prev = -1.0
    for delta in (-3.0, -1.0, 0.0, 0.5, 0.83, 1.23, 3.0):
        pa = power_cell(delta, SE_PRIMARY)["p_adopt"]
        if pa < prev - 1e-12:
            p.append("power_cell p_adopt is not monotone increasing in delta")
        prev = pa
    # the primary really is better powered than the screen at the prior
    if (power_cell(PRIOR_CENTRAL, SE_PRIMARY)["p_adopt"]
            <= power_cell(PRIOR_CENTRAL, SE_SCREEN)["p_adopt"]):
        p.append("the PRIMARY cell is not better powered than the SCREEN at "
                 "the planning prior — check n_decks/SE")
    # the honesty claim the riders and PREREG §4.4 make, asserted mechanically
    if power_cell(0.0, SE_PRIMARY)["p_unresolved"] < 0.45:
        p.append("PREREG §4.4 and RIDERS_BY_BRANCH['B-UNRESOLVED'] claim a "
                 "true null reads UNRESOLVED roughly 60% of the time at the "
                 "primary's n; power_cell no longer agrees — fix the prose or "
                 "the design, do not let them drift")

    # --- MDE / Type-M tripwire ---------------------------------------------
    m80 = mde(SE_PRIMARY)
    if not (1.2 < m80 < 1.7):
        p.append(f"mde(SE_PRIMARY) {m80} is outside the ~1.39 the design "
                 "documents — check the derivation")
    if not (m80 > PRIOR_NO_DECAY):
        p.append("the primary's 80%-power MDE is no longer above the "
                 "no-decay prior — the Type-M tripwire's premise is stale")
    if abs(power_cell(m80, SE_PRIMARY)["p_adopt"] - 0.80) > 1e-3:
        p.append("mde() and power_cell() disagree about the 80% point")

    # --- paired_difference basics -------------------------------------------
    a = {1: 2.0, 2: 4.0, 3: 6.0, 9: 1.0}
    b = {1: 1.0, 2: 1.0, 3: 1.0}
    m, z, n, se, _ = paired_difference(a, b)
    if n != 3 or abs(m - 3.0) > 1e-9:
        p.append(f"paired_difference on a fixture gave n={n} mean={m}, want 3/3.0")
    if paired_difference({1: 1.0}, {1: 1.0})[2] != 1:
        p.append("paired_difference did not intersect on a single deck")

    return p
