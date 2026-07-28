"""Executable production-champion factory (Track-F item F1, 2026-07-19).

ONE place that reads ``governance/PRODUCTION.yaml`` — the single source of truth for
"who is the champion" — and INSTANTIATES the agent, emitting a *resolved runtime
manifest* whose hashes and leaf values are computed on REAL boards at construction,
not read off a label. This is the classical-champion analogue of
``eval_provenance.py``'s R1/R7 guards (the 2026-06-07 review's "the manifest recorded
labels, not the function that executed"): the factory PROVES, at build time, that the
agent it hands back runs the curve125 v2.9 Bmild_cap8 leaf the governance file names.

Any mismatch RAISES (never warns) — a ``ProvenanceError`` from ``eval_provenance``.

Two guards, deepest-first (the ruler-trap lesson, STATUS 2026-07-17):
  1. **Semantic** (authoritative, robust to LeafConfig dataclass drift): the resolved
     leaf's meeple-curve VALUES == the frozen curve125, caps == 8/8, value_blend == 0,
     residual_scale == 0, AND a panel of leaf OUTPUTS on canonical boards == golden.
  2. **Fingerprint** (fragile-by-design, so it forces a re-review on any config-shape
     change): three hash dialects of the same leaf are asserted. A hash drift with the
     semantic checks still green is almost always an additive default-off LeafConfig
     field (the 158f17ff precedent) — the raise message says so and the fix is to
     re-baseline the constant here after review, exactly what this F1 build did.

TWO-DIALECT HASH STORY (all three runtime-verified 2026-07-19, they describe the SAME
leaf function — meeple_k is inert under a non-null curve, 240/240 byte-identical):
  * ``a36d2e15a3b3d71d`` = ``c5_leaf_override._leaf_hash`` (ALL fields, meeple_k=2.0) —
    the eval-harness dialect; what STATUS verifies, tests/test_t3_optuna corroborates,
    and every real C7 curve125 manifest carries.
  * ``6dfffd57051690f2`` = ``snapshot._frozen_config_hash`` with meeple_k=0.0 — the
    champ_env.sh / distill-gen dialect (champ_env.sh does not export
    CARCASSONNE_V25_MEEPLE_K, so it resolves 0.0).
  * ``158f17ff76adaa02`` = ``snapshot._frozen_config_hash`` with meeple_k=2.0 — the
    value PRODUCTION.yaml historically recorded. It is REPRODUCIBLE (not "gone stale"),
    but it is a nonstandard sub-dialect nobody else references; the F1 correction moves
    the YAML to the harness dialect (a36d2e15) + records all three here.

USAGE — the caller MUST set the production leaf env before importing carcassonne_ai
(every harness does this via os.environ.setdefault, and scripts/human_anchor/
env_preamble.py does it for the human path). The factory does not mutate the env
(DEFAULT_CONFIG is import-frozen) — it builds ``dc.replace(DEFAULT_CONFIG,
v29_meeple_curve=curve125)`` exactly as eval_fair_puct does, then verifies. If the env
was not set the verify raises with an instruction to set it.

    agent = make_production_champion("fair", game=Game(enable_legal_moves_cache=True),
                                     seed=101)
    agent.manifest   # the resolved runtime manifest (also returned by resolved_manifest())
"""
from __future__ import annotations

import dataclasses as dc
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import eval_provenance as ep
from .virtual_score_v2 import DEFAULT_CONFIG

REPO = Path(__file__).resolve().parents[2]
PRODUCTION_YAML = REPO / "governance" / "PRODUCTION.yaml"

# The frozen production leaf shape (governance/PRODUCTION.yaml champion.leaf_config).
CURVE125 = (-10.0, -5.0, -1.25, 0.0, 2.5, 3.75, 5.0, 6.25)
CURVE100 = (-8.0, -4.0, -1.0, 0.0, 2.0, 3.0, 4.0, 5.0)   # the frozen v2.9 (rung) curve

# Canonical leaf-config hashes — all three RUNTIME-VERIFIED 2026-07-19 (see the module
# docstring's two-dialect story). These are the F1 fingerprints; a mismatch raises.
LEAF_HASH_HARNESS = "a36d2e15a3b3d71d"        # _leaf_hash, all fields, meeple_k=2.0
LEAF_HASH_FROZEN_MK0 = "6dfffd57051690f2"     # _frozen_config_hash, meeple_k=0.0 (champ_env)
LEAF_HASH_FROZEN_MK2 = "158f17ff76adaa02"     # _frozen_config_hash, meeple_k=2.0 (old YAML value)

# Runtime leaf-VALUE panel (the deepest guard — a curve/cap change flips these even if
# the config hash were spoofed). Empty board, meeples-in-hand=(p0,p1); the meeple curve
# maps hand count -> value, so diff == curve125[p0] - curve125[p1]. Captured 2026-07-19.
_LEAF_VALUE_PANEL = {
    "empty_meeples_3v7_float": ((3, 7), "float", -6.25),
    "empty_meeples_7v3_float": ((7, 3), "float", 6.25),
    "empty_meeples_0v7_int": ((0, 7), "int", -16),
    "empty_meeples_5v5_float": ((5, 5), "float", 0.0),
}

MANIFEST_SCHEMA = "carcassonne-champion-factory/v1"


# --------------------------------------------------------------------------- #
# PRODUCTION.yaml -> a resolved spec                                            #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ProductionSpec:
    champion_id: str
    # search knobs (champion.agent_knobs)
    c_puct: float
    tau_p: float
    final_select: str
    leaf_quantize: str
    value_norm: float
    reuse_tree: bool
    # leaf (champion.leaf_config)
    curve: tuple
    bonus_cap: float
    opp_bonus_cap: float
    # fair deploy (champion.fair_deploy)
    k_dets: int
    sims_per_det: int
    exact_max_k: int
    # provenance
    yaml_leaf_hash: str
    env_knobs: dict


def load_production_spec(path: Path | None = None) -> ProductionSpec:
    """Parse governance/PRODUCTION.yaml into a resolved ProductionSpec (single source)."""
    import yaml

    path = Path(path) if path is not None else PRODUCTION_YAML
    doc = yaml.safe_load(path.read_text())
    champ = doc["champion"]
    knobs = champ["agent_knobs"]
    leafc = champ["leaf_config"]
    fair = champ["fair_deploy"]
    return ProductionSpec(
        champion_id=str(champ["id"]),
        c_puct=float(knobs["c_puct"]),
        tau_p=float(knobs["tau_p"]),
        final_select=str(knobs["final_select"]),
        leaf_quantize=str(knobs["leaf_quantize"]),
        value_norm=float(knobs["value_norm"]),
        reuse_tree=bool(knobs.get("reuse_tree", False)),
        curve=tuple(float(x) for x in leafc["v29_meeple_curve"]),
        bonus_cap=float(leafc["bonus_cap"]),
        opp_bonus_cap=float(leafc["opp_bonus_cap"]),
        k_dets=int(fair["k_dets"]),
        sims_per_det=int(fair["sims_per_det"]),
        # PRODUCTION.yaml prose: "exact K<=2 MARGINALIZED expectiminimax handoff".
        # K<=2 is both the tractability frontier and the L2-3 validation band; there is
        # no separate YAML scalar for it, so it is pinned here (asserted <=2 below).
        exact_max_k=2,
        yaml_leaf_hash=str(champ.get("leaf_hash", "")),
        env_knobs=dict(champ.get("env_knobs", {})),
    )


# --------------------------------------------------------------------------- #
# Leaf-hash helpers — imported from the SINGLE-SOURCE script modules (the same #
# dialect the harnesses speak), with an inline fallback so the factory still    #
# works when scripts/ is not importable. A release test asserts they agree.     #
# --------------------------------------------------------------------------- #
def _hashers():
    """Return (_leaf_hash, _frozen_config_hash) from the authoritative script modules.

    Precedent: fair_agent.py lazily inserts scripts/level2 for endgame_solver. We do the
    same for the two hash dialects so there is ONE definition, not a copy."""
    for rel in ("scripts/classical_search", "scripts/measurement_infra"):
        p = str(REPO / rel)
        if p not in sys.path:
            sys.path.insert(0, p)
    from c5_leaf_override import _leaf_hash
    from snapshot import _frozen_config_hash
    return _leaf_hash, _frozen_config_hash


def _config_hash(manifest_dict: dict) -> str:
    """Stable short hash of the resolved HeuristicPriorConfig manifest."""
    return hashlib.sha256(
        json.dumps(manifest_dict, sort_keys=True, default=str).encode()
    ).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# The production leaf + prior config                                            #
# --------------------------------------------------------------------------- #
def production_leaf_cfg(spec: ProductionSpec | None = None):
    """The frozen curve125 champion LeafConfig = env DEFAULT_CONFIG with ONLY the meeple
    curve replaced — byte-identical to eval_fair_puct._curve125_leaf_cfg(). The caller
    must have set the production leaf env (cap8 etc.) before importing carcassonne_ai;
    resolved_manifest(verify=True) fails loud if not."""
    spec = spec or load_production_spec()
    return dc.replace(DEFAULT_CONFIG, v29_meeple_curve=tuple(spec.curve))


def production_prior_cfg(spec: ProductionSpec | None = None, leaf_cfg=None):
    """The champion HeuristicPriorConfig (c1.5/tau5/float/visits/vn15) with the curve125
    leaf. reuse_tree rides from the YAML (True) but is INERT in fair deploy (the fair
    agent runs fresh per-determinization trees and never reads it)."""
    from .heuristic_prior_mcts import HeuristicPriorConfig

    spec = spec or load_production_spec()
    if leaf_cfg is None:
        leaf_cfg = production_leaf_cfg(spec)
    return HeuristicPriorConfig(
        c_puct=spec.c_puct,
        tau_p=spec.tau_p,
        leaf_quantize=spec.leaf_quantize,
        final_select=spec.final_select,
        value_norm=spec.value_norm,
        leaf_cfg=leaf_cfg,
        reuse_tree=spec.reuse_tree,
    )


# --------------------------------------------------------------------------- #
# Runtime verification (the R1/R7-class guard, extended to the classical champ) #
# --------------------------------------------------------------------------- #
def _leaf_value_panel(leaf_cfg) -> dict:
    """Evaluate the frozen leaf on a fixed panel of deterministic boards. The panel
    isolates the meeple curve (empty board, hand counts differ), so a curve/cap change
    is caught even if a config hash were spoofed."""
    from wingedsheep.carcassonne.carcassonne_game_state import CarcassonneGameState
    from wingedsheep.carcassonne.tile_sets.supplementary_rules import SupplementaryRule
    from wingedsheep.carcassonne.tile_sets.tile_sets import TileSet

    from . import flat_leaf

    def _empty(meeples):
        st = CarcassonneGameState(
            tile_sets=(TileSet.BASE,),
            supplementary_rules=(SupplementaryRule.FARMERS,), players=2)
        for r in range(len(st.board)):
            for c in range(len(st.board[0])):
                st.board[r][c] = None
        st.placed_meeples = [[], []]
        st.scores = [0, 0]
        st.next_tile = None
        st.meeples = list(meeples)
        return st

    out = {}
    for label, (meeples, kind, _golden) in _LEAF_VALUE_PANEL.items():
        st = _empty(meeples)
        if kind == "float":
            out[label] = float(flat_leaf.flat_virtual_score_v2_float(st, 0, leaf_cfg))
        else:
            out[label] = int(flat_leaf.flat_virtual_score_v2(st, 0, leaf_cfg))
    return out


def verify_leaf(leaf_cfg, spec: ProductionSpec | None = None) -> dict:
    """RAISE ``ProvenanceError`` unless ``leaf_cfg`` is the frozen production curve125
    champion leaf, by BOTH the semantic panel and the three fingerprints. Returns the
    provenance dict (hashes + panel) for the manifest."""
    spec = spec or load_production_spec()

    # --- 1. semantic guard (authoritative; robust to LeafConfig dataclass drift) ---
    curve = tuple(float(x) for x in (leaf_cfg.v29_meeple_curve or ()))
    if curve != CURVE125:
        raise ep.ProvenanceError(
            f"champion leaf curve is {curve!r}, expected the frozen curve125 {CURVE125!r}. "
            "Did you forget to set the production leaf env (CARCASSONNE_V29_MEEPLE_CURVE / "
            "CAP / OPP_CAP) before importing carcassonne_ai? DEFAULT_CONFIG is import-frozen."
        )
    for field, want in (("bonus_cap", spec.bonus_cap), ("opp_bonus_cap", spec.opp_bonus_cap)):
        got = float(getattr(leaf_cfg, field))
        if got != want:
            raise ep.ProvenanceError(
                f"champion leaf {field}={got} != PRODUCTION.yaml {want}. The production "
                "leaf env (CARCASSONNE_V25_CAP/OPP_CAP=8) is not set — set it before import."
            )
    for field in ("value_blend", "residual_scale"):
        got = float(getattr(leaf_cfg, field, 0.0) or 0.0)
        if got != 0.0:
            raise ep.ProvenanceError(
                f"champion leaf {field}={got} != 0 — the classical champion is a pure "
                "heuristic leaf (no learned value blend/residual).")

    panel = _leaf_value_panel(leaf_cfg)
    for label, (_m, _k, golden) in _LEAF_VALUE_PANEL.items():
        if panel[label] != golden:
            raise ep.ProvenanceError(
                f"champion leaf VALUE drift on {label}: got {panel[label]!r}, golden "
                f"{golden!r}. The curve values matched but the leaf OUTPUT changed — a "
                "non-curve leaf change (cap/term). Re-baseline only after review.")

    # --- 2. fingerprint guard (fragile-by-design: forces re-review on config-shape drift)
    _leaf_hash, _frozen_config_hash = _hashers()
    lh_harness = _leaf_hash(leaf_cfg)
    lh_frozen_mk2 = _frozen_config_hash(leaf_cfg)
    lh_frozen_mk0 = _frozen_config_hash(dc.replace(leaf_cfg, meeple_k=0.0))
    hashes = {
        "harness_leaf_hash": lh_harness,          # a36d2e15 dialect (STATUS-verified)
        "frozen_config_hash_meeple_k0": lh_frozen_mk0,  # 6dfffd57 (champ_env/distill)
        "frozen_config_hash_meeple_k2": lh_frozen_mk2,  # 158f17ff (old YAML value)
    }
    expected = {
        "harness_leaf_hash": LEAF_HASH_HARNESS,
        "frozen_config_hash_meeple_k0": LEAF_HASH_FROZEN_MK0,
        "frozen_config_hash_meeple_k2": LEAF_HASH_FROZEN_MK2,
    }
    drift = [f"{k}: got {v} != expected {expected[k]}" for k, v in hashes.items()
             if v != expected[k]]
    if drift:
        raise ep.ProvenanceError(
            "champion leaf FINGERPRINT drift (" + "; ".join(drift) + "). The semantic "
            "panel passed, so this is almost certainly an additive default-off LeafConfig "
            "field reshaping the hash (the 158f17ff precedent). Re-baseline the "
            "champion_factory hash constants AFTER review — this is a release gate, not a "
            "warning.")
    return {"hashes": hashes, "leaf_value_panel": panel}


def resolved_manifest(mode: str, spec: ProductionSpec | None = None,
                      leaf_cfg=None, cfg=None, *, verify: bool = True) -> dict:
    """The resolved runtime manifest for a production champion. Deterministic (no
    timestamps) so it is byte-stable across constructions. verify=True runs verify_leaf
    (raises on any mismatch); pass verify=False only to INSPECT an off-spec config."""
    if mode not in ("fair", "clairvoyant"):
        raise ValueError(f"mode must be 'fair'|'clairvoyant'; got {mode!r}")
    spec = spec or load_production_spec()
    if leaf_cfg is None:
        leaf_cfg = production_leaf_cfg(spec)
    if cfg is None:
        cfg = production_prior_cfg(spec, leaf_cfg)
    if spec.exact_max_k > 2:
        raise ep.ProvenanceError(
            f"fair endgame exact_max_k={spec.exact_max_k} > 2 — the fair marginalized "
            "solve is only honest/tractable at K<=2 (a K>=3 solve would read the true deck).")

    leaf_prov = verify_leaf(leaf_cfg, spec) if verify else {
        "hashes": None, "leaf_value_panel": _leaf_value_panel(leaf_cfg)}
    commit, dirty = ep.git_commit_and_dirty()
    total_sims = spec.k_dets * spec.sims_per_det
    return {
        "schema": MANIFEST_SCHEMA,
        "mode": mode,
        "source": "governance/PRODUCTION.yaml",
        "champion_id": spec.champion_id,
        "agent_class": ("FairHeuristicPriorAgent" if mode == "fair"
                        else "HeuristicPriorAgent"),
        "reshuffle_semantics": (
            "root-determinization PIMC: reshuffle the UNSEEN deck (canonical sort + rng), "
            "next_tile untouched; fresh tree per determinization; pooled-Q pick"
            if mode == "fair"
            else "clairvoyant descent of the true engine deck (dev/ruler only)"),
        "search": {
            "c_puct": spec.c_puct, "tau_p": spec.tau_p,
            "leaf_quantize": spec.leaf_quantize, "final_select": spec.final_select,
            "value_norm": spec.value_norm, "reuse_tree": spec.reuse_tree,
            # reuse_tree is a NO-OP in fair deploy (fresh per-det trees); honest flag:
            "reuse_tree_effective": bool(spec.reuse_tree and mode == "clairvoyant"),
            "config_hash": _config_hash(cfg.as_manifest()),
        },
        "fair_deploy": {
            "k_dets": spec.k_dets, "sims_per_det": spec.sims_per_det,
            "total_sims": total_sims, "exact_max_k": spec.exact_max_k,
            "endgame": "marginalized expectiminimax (honest hidden-bag), no alpha-beta",
        },
        "leaf": {
            "curve125": list(CURVE125),
            "bonus_cap": spec.bonus_cap, "opp_bonus_cap": spec.opp_bonus_cap,
            "value_blend": float(getattr(leaf_cfg, "value_blend", 0.0) or 0.0),
            "residual_scale": float(getattr(leaf_cfg, "residual_scale", 0.0) or 0.0),
        },
        "leaf_hashes": leaf_prov["hashes"],
        "leaf_value_panel": leaf_prov["leaf_value_panel"],
        "code_commit": commit,
        "dirty": dirty,
        "env_knobs": spec.env_knobs,
        # R1/R7 lineage: like eval_provenance, this manifest records the leaf that WILL
        # execute (verified on real boards), not a label — extended to the classical champ.
        "provenance_note": "runtime-verified leaf (curve values + panel + 3 hash dialects); "
                           "R1/R7-class guard for the classical champion (champion_factory).",
    }


# --------------------------------------------------------------------------- #
# Thin agent builders — the SINGLE construction point for the champion agent.   #
# Byte-identical to a direct FairHeuristicPriorAgent/HeuristicPriorAgent call    #
# (they forward verbatim); eval_fair_puct routes its constructions through here. #
# --------------------------------------------------------------------------- #
_UNSET = object()


def _default_exact_budget() -> int:
    """The solver node budget an agent uses when nobody passes one. READ from
    fair_agent (point-don't-copy) so the manifest can never quote a stale figure."""
    from .fair_agent import DEFAULT_EXACT_BUDGET

    return int(DEFAULT_EXACT_BUDGET)


def build_fair_champion(game, *, cfg=None, sims=_UNSET, k_dets=_UNSET, seed=_UNSET,
                        exact_endgame=_UNSET, exact_max_k=_UNSET,
                        min_pooled_visits=_UNSET, exact_budget=_UNSET,
                        net=_UNSET, evaluator=_UNSET, sighted_game=_UNSET,
                        batch_size=_UNSET, batch_evaluator=_UNSET,
                        virtual_loss=_UNSET,
                        oracle_prior_mult=_UNSET, oracle_prior_eps_coef=_UNSET,
                        meeple_dedup=_UNSET, intra_reuse=_UNSET):
    """Construct the fair-play PIMC champion (FairHeuristicPriorAgent). Only kwargs the
    caller actually sets are forwarded, so any left at ``_UNSET`` fall through to the
    agent's OWN defaults — i.e. constructing via this factory is byte-for-byte identical
    to constructing FairHeuristicPriorAgent directly (the parity contract for the
    eval_fair_puct migration). ``cfg=None`` defaults to the production curve125 config."""
    from .fair_agent import FairHeuristicPriorAgent

    if cfg is None:
        cfg = production_prior_cfg()
    kw = {k: v for k, v in dict(
        sims=sims, k_dets=k_dets, seed=seed, exact_endgame=exact_endgame,
        exact_max_k=exact_max_k, min_pooled_visits=min_pooled_visits,
        exact_budget=exact_budget, net=net, evaluator=evaluator,
        sighted_game=sighted_game, batch_size=batch_size,
        batch_evaluator=batch_evaluator, virtual_loss=virtual_loss,
        oracle_prior_mult=oracle_prior_mult,
        oracle_prior_eps_coef=oracle_prior_eps_coef,
        meeple_dedup=meeple_dedup, intra_reuse=intra_reuse,
    ).items() if v is not _UNSET}
    return FairHeuristicPriorAgent(game, cfg, **kw)


def build_clairvoyant_champion(game, *, cfg=None, simulations, seed=_UNSET,
                               reuse_tree=_UNSET, meeple_dedup=_UNSET):
    """Construct the clairvoyant PUCT champion (HeuristicPriorAgent) — the dev/ruler
    agent (reads the true deck). Byte-identical to a direct construction; ``cfg=None``
    defaults to the production curve125 config."""
    from .heuristic_prior_mcts import HeuristicPriorAgent

    if cfg is None:
        cfg = production_prior_cfg()
    kw = {k: v for k, v in dict(seed=seed, reuse_tree=reuse_tree,
                                meeple_dedup=meeple_dedup).items()
          if v is not _UNSET}
    return HeuristicPriorAgent(game, cfg, simulations=int(simulations), **kw)


# --------------------------------------------------------------------------- #
# The high-level entry point                                                    #
# --------------------------------------------------------------------------- #
def make_production_champion(mode: str, *, game=None, seed: int = 0,
                             sims: int | None = None, k_dets: int | None = None,
                             exact_endgame: bool = True, verify: bool = True,
                             meeple_dedup: bool | None = None,
                             intra_reuse: bool | None = None,
                             exact_budget: int | None = None):
    """Instantiate the production champion named by governance/PRODUCTION.yaml and attach
    its resolved runtime manifest (``agent.manifest``). ``verify=True`` PROVES the leaf on
    real boards at construction and RAISES on any mismatch.

    mode="fair"        -> FairHeuristicPriorAgent (deployable PIMC, k4x688, exact-K<=2).
    mode="clairvoyant" -> HeuristicPriorAgent (dev/ruler; k_dets*sims_per_det total sims).

    ``game`` defaults to a fresh Game(enable_legal_moves_cache=True). ``sims``/``k_dets``
    override the YAML budget (e.g. a smoke); the manifest still records the YAML config.

    ``meeple_dedup`` binds the MEEPLE-DEDUP search feature for THIS agent
    (None = inherit ``CARCASSONNE_MEEPLE_DEDUP``, which defaults OFF). It is stamped
    onto the attached manifest ONLY when it resolves ON, so an OFF champion's manifest
    — and every hash computed from it — is byte-identical to before the feature existed.

    ``intra_reuse`` binds the C3-INTRA within-turn tree carry for THIS agent
    (None = inherit ``CARCASSONNE_INTRA_TURN_REUSE``, which defaults OFF). FAIR MODE ONLY
    — the carry lives in the PIMC agent's two-decisions-per-turn structure, which the
    clairvoyant single-search agent does not have; passing it with mode="clairvoyant"
    raises rather than silently doing nothing. Stamped onto the manifest ONLY when it
    resolves ON, on the same no-hash-drift terms as ``meeple_dedup``.

    ``exact_budget`` caps the endgame solver's NODE budget for this agent
    (None = do not pass it at all, i.e. the agent's own
    ``fair_agent.DEFAULT_EXACT_BUDGET`` = 2,000,000 — byte-identical to before this
    kwarg existed). It exists because the budget was previously unreachable through
    this entry point, so an embedder (the Android app) could not bound a solve; the
    largest solve observed to date is 7,067 nodes (2,214 across the memo's 9 endgames,
    7,067 in a later 3-position probe), but the budget has NO wall-clock component and
    there is no mid-search cancel, so an unlucky board is an unbounded hang on a device
    the user is holding (measurement/ANDROID_WALLCLOCK_MEMO_20260728.md §3). It is a SAFETY bound, not a
    speedup: if it ever fires, the agent takes its documented ``BudgetExceeded`` ->
    fair-PIMC fallback for that ONE decision, which CHANGES PLAY — so it is stamped
    onto the manifest whenever it is set. FAIR MODE ONLY (the clairvoyant agent has
    no endgame solver); passing it with mode="clairvoyant" raises rather than
    silently doing nothing."""
    from . import intra_reuse as intra_carry
    from . import meeple_equiv
    from .game_wrapper import Game

    spec = load_production_spec()
    if game is None:
        game = Game(enable_legal_moves_cache=True)
    leaf_cfg = production_leaf_cfg(spec)
    cfg = production_prior_cfg(spec, leaf_cfg)
    manifest = resolved_manifest(mode, spec, leaf_cfg, cfg, verify=verify)

    # Left at _UNSET when the caller said nothing, so the agent constructor is called
    # with EXACTLY the argument list it had before this feature existed.
    dedup_kw = {} if meeple_dedup is None else {"meeple_dedup": bool(meeple_dedup)}
    intra_kw = {} if intra_reuse is None else {"intra_reuse": bool(intra_reuse)}
    budget_kw = {} if exact_budget is None else {"exact_budget": int(exact_budget)}
    if intra_reuse is not None and mode != "fair":
        raise ValueError(
            "intra_reuse is a FAIR-mode feature (the within-turn carry needs the PIMC "
            f"agent's tile+meeple decision pair); got mode={mode!r}")
    if exact_budget is not None and mode != "fair":
        raise ValueError(
            "exact_budget is a FAIR-mode feature (only the PIMC agent runs the endgame "
            f"solver); got mode={mode!r}")

    if mode == "fair":
        agent = build_fair_champion(
            game, cfg=cfg,
            sims=(spec.sims_per_det if sims is None else int(sims)),
            k_dets=(spec.k_dets if k_dets is None else int(k_dets)),
            seed=int(seed), exact_endgame=bool(exact_endgame),
            exact_max_k=spec.exact_max_k, **dedup_kw, **intra_kw, **budget_kw)
    elif mode == "clairvoyant":
        total = (spec.k_dets * spec.sims_per_det) if sims is None else int(sims)
        agent = build_clairvoyant_champion(
            game, cfg=cfg, simulations=total, seed=int(seed), **dedup_kw)
    else:
        raise ValueError(f"mode must be 'fair'|'clairvoyant'; got {mode!r}")

    # The manifest's fair_deploy block records the PRODUCTION.yaml INTENT (k4x688=2752).
    # If sims/k_dets override it (a smoke), record the budget the agent ACTUALLY runs so
    # the game log never misrepresents what played. resolved_manifest itself stays
    # canonical/byte-stable (the override note is added only on the attached copy).
    if mode == "fair":
        es = spec.sims_per_det if sims is None else int(sims)
        ek = spec.k_dets if k_dets is None else int(k_dets)
        if (es, ek) != (spec.sims_per_det, spec.k_dets):
            manifest = dict(manifest)
            manifest["runtime_budget_override"] = {
                "sims_per_det": es, "k_dets": ek, "total_sims": es * ek,
                "note": "the budget the agent ACTUALLY runs; fair_deploy above is the "
                        "PRODUCTION.yaml intent (k4x688=2752)."}
    else:
        total = (spec.k_dets * spec.sims_per_det) if sims is None else int(sims)
        if total != spec.k_dets * spec.sims_per_det:
            manifest = dict(manifest)
            manifest["runtime_budget_override"] = {
                "total_sims": total,
                "note": "the budget the agent ACTUALLY runs; fair_deploy above is intent."}

    # MEEPLE-DEDUP: stamped ONLY when the feature actually resolves ON (whether from
    # the kwarg or the env flag). An OFF champion therefore carries a manifest that is
    # byte-identical to the pre-feature one — no key, no hash drift, no re-review.
    if meeple_equiv.resolve(meeple_dedup):
        manifest = dict(manifest)
        manifest["meeple_dedup"] = {
            "enabled": True,
            "prior_mode": meeple_equiv.PRIOR_MODE,
            "source": "kwarg" if meeple_dedup is not None else meeple_equiv.ENV_VAR,
            "scope": "intra-tile feature equivalence at meeple-phase nodes "
                     "(meeple_equiv.dedup_legal); the true legal mask is unchanged",
            "note": "NON-CHAMPION search variant — this agent is NOT the deployed "
                    "champion of governance/PRODUCTION.yaml.",
        }

    # C3-INTRA: same no-hash-drift terms as MEEPLE-DEDUP above — stamped only when the
    # carry actually resolves ON, so an OFF champion's manifest is byte-identical to the
    # pre-feature one. Fair mode only (guarded at the top).
    if mode == "fair" and intra_carry.resolve(intra_reuse):
        manifest = dict(manifest)
        manifest["intra_turn_reuse"] = {
            "enabled": True,
            "source": "kwarg" if intra_reuse is not None else intra_carry.ENV_VAR,
            "scope": "within-turn carry of the k_dets trees AND their determinizations "
                     "from the TILE decision into the SAME turn's MEEPLE decision "
                     "(re-rooted at the played action); fresh search on any mismatch",
            "budget_semantics": "the meeple decision still runs `sims` NEW simulations "
                                "per determinization ON TOP of the carried visits, so ON "
                                "does more total work per turn at equal nominal sims — a "
                                "positive screen requires an equal-WALL-CLOCK confirm",
            "information_legality": "no hidden information arrives between the two "
                                    "decisions (the engine draws the next tile only at "
                                    "the END of the meeple phase), unlike the ACROSS-move "
                                    "reuse of CL-044, which stays clairvoyant-only",
            "note": "NON-CHAMPION search variant — this agent is NOT the deployed "
                    "champion of governance/PRODUCTION.yaml.",
        }

    # EXACT-BUDGET: same no-hash-drift terms — stamped ONLY when the caller actually
    # bound a budget, so a champion built without the kwarg carries a manifest that is
    # byte-identical to the pre-kwarg one. Stamped even though the bound is expected
    # never to fire, because the branch where it DOES fire changes play.
    if exact_budget is not None:
        manifest = dict(manifest)
        manifest["exact_budget"] = {
            "nodes": int(exact_budget),
            "default": int(_default_exact_budget()),
            "source": "kwarg",
            "scope": "per-solve NODE budget for the exact endgame solver; on exhaustion "
                     "the agent raises its documented BudgetExceeded and falls back to "
                     "fair PIMC for THAT ONE decision",
            "note": "a bound, not a speedup. It is expected never to fire (largest solve "
                    "observed to date = 7,067 nodes); if it DOES fire the move is a PIMC "
                    "fallback, not the champion's exact answer.",
        }

    agent.manifest = manifest
    return agent
