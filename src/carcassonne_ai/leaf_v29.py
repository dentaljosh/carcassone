"""leaf_v29 — opt-in, individually-ablatable v2.9 evaluator candidates.

Built on top of the FROZEN v2.7 / v2.8 leaf (`virtual_score_v2`). Every term here
is gated by a `LeafConfig.v29_*` field that defaults to neutral, so when none is set
`_v29_active(cfg)` is False, this module is never called, and the leaf is
byte-identical to production v2.8. None of these terms touch `flat_leaf.py`
(the v2.9 configs force the engine/object path, same pattern as the `v28_*` knobs).

Design goals (V29 spec, 2026-06-25):
  - Each candidate is one toggle, ablatable in isolation.
  - `decompose_v29` returns EVERY component separately so an audit can see which
    term moved a decision.
  - Point margin is a diagnostic; winrate is the throne. These terms are judged by
    paired full-game winrate vs h6400_v2.8, not by margin or trap-score.

Candidates (see V29_CANDIDATE_TERMS.md):
  A  v29_util_tanh_t   — win-shaped utility: total -> T*tanh(total/T) (point-scale).
  B  v29_meeple_curve  — nonlinear meeple liquidity: value-by-free-count table,
                         REPLACES the flat meeple_k term.
  D  v29_punish_k      — sparse high-confidence tactical-punish swing (STUB, see note).
  E  v29_farm_access_k — farm access / denial window (STUB, low prior — see code map §5).

Pre-killed (NOT implemented here, do not re-run): deck-aware completion probability
(Candidate C) is a confirmed null (DECISIONS 2026-05-17, re-confirmed 2026-06-22);
the existing `closure_continuous_slack` knob already covers it.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .virtual_score_v2 import LeafConfig


# ---------------------------------------------------------------------------
# Candidate A — win-shaped utility transform
# ---------------------------------------------------------------------------
def _util_transform(score: float, t: float) -> float:
    """T*tanh(score/T): preserves point-scale for |score| << T (≈ identity),
    smoothly caps magnitude at ±T for big leads. Composed downstream with the
    consumer's tanh(./15): HeuristicMCTS value = tanh(T*tanh(diff/T)/15).
    Smaller T = stronger anti-padding / more binary; larger T -> baseline."""
    if t <= 0.0:
        return score
    return t * math.tanh(score / t)


# ---------------------------------------------------------------------------
# Candidate B — nonlinear meeple liquidity curve
# ---------------------------------------------------------------------------
def _curve_lookup(curve, n: int) -> float:
    """Value of holding `n` free meeples, from a table indexed by count.
    Clamps n into [0, len-1] (free-meeple count is 0..7 in base+farmers)."""
    if n < 0:
        n = 0
    elif n >= len(curve):
        n = len(curve) - 1
    return float(curve[n])


def _meeple_curve_term(state, player: int, opp: int, curve) -> float:
    """Symmetric differential of the liquidity curve. REPLACES the flat
    meeple_k*(m_self - m_opp) term (the caller omits the flat term when a curve
    is set). `state.meeples[i]` = free/unplaced meeples (start 7)."""
    return _curve_lookup(curve, state.meeples[player]) - _curve_lookup(curve, state.meeples[opp])


# ---------------------------------------------------------------------------
# Candidate D — sparse high-confidence tactical punish (STUB)
# ---------------------------------------------------------------------------
def _punish_signal(state, player: int, opp: int, cfg: "LeafConfig") -> float:
    """STUB (returns 0.0). Second-wave: a LEAF-state term for "I just punished a
    weak/exposed opponent" largely duplicates the base score (completing a feature
    or claiming an exposed farm already banks points in `base`). The 2026-06-25
    strategic-ladder evidence (h6400 takes MUST_PUNISH_WEAK 92% vs RoD1 84%) points
    at a SEARCH/POLICY gap, not a leaf gap — so a leaf term is the wrong lever here.
    Kept as a toggle so the hypothesis can be tested if A/B show the leaf has room.
    Do not enable without an inspectable example set (spec Part B: examples first)."""
    return 0.0


# ---------------------------------------------------------------------------
# Candidate E — farm access / denial window (STUB, low prior)
# ---------------------------------------------------------------------------
def _farm_access_signal(state, player: int, opp: int, cfg: "LeafConfig") -> float:
    """STUB (returns 0.0). Low prior: farm-majority-gate and opp-denial were both
    KILLED in the 2026-06-22 v2.8 program (code map §5). Reserved for an access-
    WINDOW formulation (unclaimed high-value field with legal farmer access, merge
    swing) only if A/B prove the leaf is leaving winrate on the table."""
    return 0.0


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def apply_v29(state, player: int, opp: int, cfg: "LeafConfig", score: float) -> float:
    """Add the active v2.9 terms to the (base + closure ± + flat-meeple-if-no-curve)
    score, then apply the win-shaping transform LAST (on the full total).

    Called from `virtual_score_v2` only when `_v29_active(cfg)`. The caller has
    already omitted the flat meeple_k term iff a curve is set."""
    if cfg.v29_meeple_curve is not None:          # B (replaces flat meeple)
        score += _meeple_curve_term(state, player, opp, cfg.v29_meeple_curve)
    if cfg.v29_punish_k != 0.0:                   # D (stub)
        score += cfg.v29_punish_k * _punish_signal(state, player, opp, cfg)
    if cfg.v29_farm_access_k != 0.0:              # E (stub)
        score += cfg.v29_farm_access_k * _farm_access_signal(state, player, opp, cfg)
    if cfg.v29_util_tanh_t > 0.0:                 # A (last, on full total)
        score = _util_transform(score, cfg.v29_util_tanh_t)
    return score


def decompose_v29(state, player: int, cfg: "LeafConfig") -> dict:
    """Return every leaf component separately for the v2.9 audit ("which term moved
    the decision"). Recomputes each piece independently — slower than the production
    path, diagnostic-only. Sum of additive components + utility_transform_delta ==
    pre-round total; `total_int` == what `virtual_score_v2(state, player, cfg)` returns.

    Keys:
      base                  v1 end-of-game score differential
      closure_self          capped self closure-anticipation bonus
      closure_opp           capped opp closure-anticipation bonus  (subtracted)
      meeple_flat           v2.8 flat meeple term meeple_k*(m_self-m_opp) (reference)
      meeple_curve_delta    (curve term - meeple_flat) when a curve is set, else 0
      deck_completion_delta 0.0 (Candidate C pre-killed — not a v2.9 term)
      tactical_punish_delta D term (0.0 stub)
      threat_block_delta    alias of the block half of D (0.0 stub; kept for the spec schema)
      farm_access_delta     E term (0.0 stub)
      phase_scaling_delta   0.0 (no phase-scaling candidate active)
      pretransform_total    base+closure_self-closure_opp+meeple+deltas (before A)
      utility_transform_delta  A: T*tanh(pretransform/T) - pretransform (0 if A off)
      total                 pretransform_total + utility_transform_delta (float)
      total_int             int(round(total)) == virtual_score_v2 output
    """
    from .virtual_score import virtual_score
    from .virtual_score_v2 import _capped, _closure_anticipation_bonus

    opp = 1 - player
    base = float(virtual_score(state, player))
    closure_self = _capped(_closure_anticipation_bonus(state, player, cfg), cfg.bonus_cap)
    closure_opp = _capped(_closure_anticipation_bonus(state, opp, cfg), cfg.opp_bonus_cap)

    # meeple: flat reference always computed; curve delta only when a curve is set.
    m_self, m_opp = state.meeples[player], state.meeples[opp]
    meeple_flat = cfg.meeple_k * (m_self - m_opp) if cfg.meeple_k > 0.0 else 0.0
    if cfg.v29_meeple_curve is not None:
        curve_term = _meeple_curve_term(state, player, opp, cfg.v29_meeple_curve)
        meeple_curve_delta = curve_term - meeple_flat
        meeple_contribution = curve_term
    else:
        meeple_curve_delta = 0.0
        meeple_contribution = meeple_flat

    # v28 recovery-scaled meeple (independent of legacy meeple_k); included so the
    # decomposition total matches virtual_score_v2 for v28-active cfgs too.
    v28_meeple = 0.0
    if cfg.v28_meeple_k != 0.0:
        rf = 1.0
        if cfg.v28_meeple_recovery_t0 > 0:
            rf = min(1.0, len(state.deck) / cfg.v28_meeple_recovery_t0)
        v28_meeple = cfg.v28_meeple_k * (m_self - m_opp) * rf

    tactical_punish_delta = cfg.v29_punish_k * _punish_signal(state, player, opp, cfg) \
        if cfg.v29_punish_k != 0.0 else 0.0
    farm_access_delta = cfg.v29_farm_access_k * _farm_access_signal(state, player, opp, cfg) \
        if cfg.v29_farm_access_k != 0.0 else 0.0

    pretransform = (base + closure_self - closure_opp + meeple_contribution + v28_meeple
                    + tactical_punish_delta + farm_access_delta)
    if cfg.v29_util_tanh_t > 0.0:
        total = _util_transform(pretransform, cfg.v29_util_tanh_t)
    else:
        total = pretransform
    utility_transform_delta = total - pretransform

    return {
        "base": base,
        "closure_self": closure_self,
        "closure_opp": closure_opp,
        "meeple_flat": meeple_flat,
        "meeple_curve_delta": meeple_curve_delta,
        "v28_meeple": v28_meeple,
        "deck_completion_delta": 0.0,
        "tactical_punish_delta": tactical_punish_delta,
        "threat_block_delta": 0.0,
        "farm_access_delta": farm_access_delta,
        "phase_scaling_delta": 0.0,
        "pretransform_total": pretransform,
        "utility_transform_delta": utility_transform_delta,
        "total": total,
        "total_int": int(round(total)),
    }
