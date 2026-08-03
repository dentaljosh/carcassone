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

# The ENGINES a champion may execute on. "auto" is not a member: it is a resolution
# REQUEST that must land on one of these before anything is built or stamped. Every
# entry point that accepts a backend validates against this one set (ROUND2 F-5) —
# `load_production_spec` deliberately does not, so that an unknown YAML value fails at
# the point of USE with a message naming the file, rather than at import.
KNOWN_BACKENDS = frozenset({"python", "rust"})


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
    # deploy EXECUTION (champion.fair_deploy.parallel_workers / .deploy_profiles), added
    # 2026-07-29 with the k8x1376 budget promotion. Parsed and exposed; NOT auto-applied —
    # see deploy_profile() and the YAML's own "WIRING STATUS" comment.
    parallel_workers: int | None = None
    deploy_profiles: dict = dc.field(default_factory=dict)
    # champion.fair_deploy.backend — the ENGINE the champion of record executes on
    # (added 2026-08-01). Absent ⇒ "python", so an older YAML resolves identically.
    # Reached only through backend="auto"; see make_production_champion.
    backend: str = "python"


def load_production_spec(path: Path | None = None) -> ProductionSpec:
    """Parse governance/PRODUCTION.yaml into a resolved ProductionSpec (single source)."""
    import yaml

    path = Path(path) if path is not None else PRODUCTION_YAML
    # encoding="utf-8" is MANDATORY, not cosmetic: Path.read_text() with no encoding
    # uses locale.getpreferredencoding(), which is cp1252 on a stock Windows CPython.
    # PRODUCTION.yaml carries non-ASCII prose, so the bare call raises UnicodeDecodeError
    # there while passing everywhere else (found 2026-07-29 by the native-Windows A/B).
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
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
        parallel_workers=(None if fair.get("parallel_workers") in (None, "")
                          else int(fair["parallel_workers"])),
        deploy_profiles=dict(fair.get("deploy_profiles") or {}),
        backend=str(fair.get("backend", "python") or "python"),
    )


# The profile an embedder asks for when it cannot pay the champion budget. The champion
# of record is always fair_deploy.k_dets/.sims_per_det; a profile that differs from it is
# a WEAKER configuration, and make_production_champion stamps `runtime_budget_override`
# onto the manifest whenever the running budget differs, so a game log can never
# misrepresent which budget played.
DEPLOY_PROFILE_DEFAULT = "desktop"


def deploy_profile(name: str = DEPLOY_PROFILE_DEFAULT,
                   spec: ProductionSpec | None = None) -> dict:
    """The named deploy EXECUTION profile from PRODUCTION.yaml, as
    ``{"k_dets", "sims_per_det", "total_sims", "parallel_workers", "backend",
    "rust_threads", "name", "found"}``.

    FAIL-SAFE, NOT FAIL-OPEN: an unknown/absent profile falls back to the champion of
    record with ``parallel_workers=None`` (i.e. the sequential, byte-identical path) and
    ``found=False``. Callers that must NEVER inherit the champion budget — the Android
    bridge is the live example, since Chaquopy has no multiprocessing — must check
    ``found`` and supply their own floor rather than trusting this default.

    ``backend`` / ``rust_threads`` (added 2026-08-01 with the mobile unpin) name the
    ENGINE a profile is executed on and how many OS threads it folds its ``k_dets``
    worlds across. Absent ⇒ ``"python"`` / ``None``, i.e. exactly the pre-field
    behaviour, so an old YAML resolves identically. ⚠️ For the ``mobile`` profile the
    two are COUPLED to the budget and must be honoured together: k8x1376 is payable on
    the Rust core (1.551 s/move, G7) and is ~25 s/move on the Python one. Reading a
    profile's budget while ignoring its ``backend`` is the failure this field exists to
    prevent; see that profile's own note."""
    spec = spec or load_production_spec()
    prof = dict((spec.deploy_profiles or {}).get(name) or {})
    k = int(prof.get("k_dets", spec.k_dets))
    s = int(prof.get("sims_per_det", spec.sims_per_det))
    pw = prof.get("parallel_workers", None)
    rt = prof.get("rust_threads", None)
    return {
        "name": str(name),
        "found": bool(prof),
        "k_dets": k,
        "sims_per_det": s,
        "total_sims": k * s,
        "parallel_workers": (None if pw in (None, "") else int(pw)),
        "backend": str(prof.get("backend", "python") or "python"),
        "rust_threads": (None if rt in (None, "") else int(rt)),
    }


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


def verify_leaf(leaf_cfg, spec: ProductionSpec | None = None, *,
                backend: str = "python") -> dict:
    """RAISE ``ProvenanceError`` unless ``leaf_cfg`` is the frozen production curve125
    champion leaf, by BOTH the semantic panel and the three fingerprints. Returns the
    provenance dict (hashes + panel) for the manifest.

    ``backend="rust"`` re-runs the VALUE PANEL through ``carc_rs`` as well. The panel is
    the deepest guard precisely because it evaluates leaf OUTPUTS on real boards rather
    than reading a label — so when the agent that will actually play computes its leaf in
    Rust, the panel has to be evaluated THERE too or it proves nothing about that agent.
    Both panels must equal the golden (rustport G2 gated them bit-equal over 3,341,772
    values; this is the runtime re-proof at construction)."""
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

    # --- 1b. the SAME semantic panel, computed by the backend that will PLAY ---
    panel_rs = None
    if backend == "rust":
        from .rust_agent import leaf_value_panel_rs

        panel_rs = leaf_value_panel_rs(leaf_cfg)
        for label, (_m, _k, golden) in _LEAF_VALUE_PANEL.items():
            if panel_rs[label] != golden:
                raise ep.ProvenanceError(
                    f"champion leaf VALUE drift on {label} in the RUST backend: got "
                    f"{panel_rs[label]!r}, golden {golden!r} (the Python panel agreed). "
                    "carc_rs is computing a different leaf than governance/PRODUCTION.yaml "
                    "names — do not play this agent.")
            if panel_rs[label] != panel[label]:
                raise ep.ProvenanceError(
                    f"champion leaf panel disagreement on {label}: python "
                    f"{panel[label]!r} != rust {panel_rs[label]!r}.")

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
    prov = {"hashes": hashes, "leaf_value_panel": panel}
    if panel_rs is not None:
        prov["leaf_value_panel_rust"] = panel_rs
    return prov


def resolved_manifest(mode: str, spec: ProductionSpec | None = None,
                      leaf_cfg=None, cfg=None, *, verify: bool = True,
                      backend: str = "python") -> dict:
    """The resolved runtime manifest for a production champion. Deterministic (no
    timestamps) so it is byte-stable across constructions. verify=True runs verify_leaf
    (raises on any mismatch); pass verify=False only to INSPECT an off-spec config.

    ``backend`` (``"python"`` default) selects which engine computes the champion. It is
    stamped ONLY when it is not the default, on the same no-hash-drift terms as
    ``parallel_workers`` — a python-backend manifest is byte-identical to the
    pre-feature one."""
    if mode not in ("fair", "clairvoyant"):
        raise ValueError(f"mode must be 'fair'|'clairvoyant'; got {mode!r}")
    spec = spec or load_production_spec()
    # make_production_champion resolves "auto" before it gets here, but this is a
    # public entry point too — and a manifest that recorded the literal string "auto"
    # would name an engine that does not exist, which is worse than either answer.
    if backend == "auto":
        backend = str(spec.backend)
    # WHITELIST (ROUND2 F-5). make_production_champion validated the resolved value but
    # this PUBLIC entry point did not, and load_production_spec accepts any string — so a
    # mistyped `fair_deploy.backend: rustt` resolved to "rustt", SKIPPED the rust panel
    # re-verification below (it branches on == "rust"), then took the `!= "python"` stamp
    # branch and wrote a manifest naming a fictional engine while quoting the G4/G6
    # behaviour-identity boilerplate. A manifest naming a backend that does not exist is
    # worse than either real answer, so this fails closed.
    if backend not in KNOWN_BACKENDS:
        raise ValueError(
            f"backend must be one of {sorted(KNOWN_BACKENDS)} (or 'auto'); got "
            f"{backend!r} — check champion.fair_deploy.backend in "
            "governance/PRODUCTION.yaml")
    if leaf_cfg is None:
        leaf_cfg = production_leaf_cfg(spec)
    if cfg is None:
        cfg = production_prior_cfg(spec, leaf_cfg)
    if spec.exact_max_k > 2:
        raise ep.ProvenanceError(
            f"fair endgame exact_max_k={spec.exact_max_k} > 2 — the fair marginalized "
            "solve is only honest/tractable at K<=2 (a K>=3 solve would read the true deck).")

    leaf_prov = verify_leaf(leaf_cfg, spec, backend=backend) if verify else {
        "hashes": None, "leaf_value_panel": _leaf_value_panel(leaf_cfg)}
    commit, dirty = ep.git_commit_and_dirty()
    total_sims = spec.k_dets * spec.sims_per_det
    man = {
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
    # BACKEND: stamped ONLY when it is not the python default (no key, no hash drift,
    # no re-review for every existing caller). The Rust backend is BEHAVIOR-IDENTICAL by
    # gate, not by construction — rustport G4 reproduced the deployed champion bit-exactly
    # (0/305,515 checks) and G6 re-proves it as 100% action agreement over full games —
    # so a log records which engine played, exactly as `parallel_workers` records which
    # execution mode did.
    if backend != "python":
        from .rust_agent import backend_provenance

        man["backend"] = {
            "name": str(backend),
            "default": "python",
            "scope": "engine only — the same PRODUCTION.yaml knobs, the same leaf "
                     "(panel re-verified through carc_rs), the same k_dets worlds "
                     "merged in the same order",
            "note": "BEHAVIOR-IDENTICAL BY GATE (rustport G4/G6), not by construction: "
                    "G4 reproduced the deployed champion bit-exactly (0/305,515 checks) "
                    "and G6 read 14,384/14,384 identical actions over 100 full games. "
                    "governance/PRODUCTION.yaml names this as the champion's execution "
                    "backend of record (2026-08-01); it is an ENGINE, not a player — no "
                    "strength claim moves with it.",
            **backend_provenance(),
        }
    if leaf_prov.get("leaf_value_panel_rust") is not None:
        man["leaf_value_panel_rust"] = leaf_prov["leaf_value_panel_rust"]
    return man


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
                        meeple_dedup=_UNSET, intra_reuse=_UNSET,
                        parallel_workers=_UNSET,
                        backend: str = "python", rust_threads: int | None = None):
    """Construct the fair-play PIMC champion (FairHeuristicPriorAgent). Only kwargs the
    caller actually sets are forwarded, so any left at ``_UNSET`` fall through to the
    agent's OWN defaults — i.e. constructing via this factory is byte-for-byte identical
    to constructing FairHeuristicPriorAgent directly (the parity contract for the
    eval_fair_puct migration). ``cfg=None`` defaults to the production curve125 config.

    ``backend`` selects the ENGINE (2026-08-02, closing the audit's F-1). Added here
    because THIS is the seam the elo-bearing harnesses actually ride: the 2026-08-01
    flip put the selector on ``make_production_champion``, but ``eval_fair_puct``,
    ``kwidth_agreement_probe`` and ``oracle_score_pilot`` all reach the agent through
    these thin builders, which had no ``backend`` parameter and therefore could not be
    moved off Python by any YAML edit (measurement/rustport_p6/
    BACKEND_BYPASS_AUDIT_20260801.md §0). Values: ``"python"`` (default, byte-identical
    to before this parameter existed), ``"rust"``, or ``"auto"`` (resolve from
    ``governance/PRODUCTION.yaml``).

    ⚠️ SAME SAFETY POSTURE AS THE FLIP, deliberately: the default stays ``"python"`` and
    ``"auto"`` is a caller ASSERTION that it drives the Rust mirror — ``start_game()``
    once, then ``advance()`` for EVERY applied action of BOTH seats. ``RustFairAgent`` is
    not a drop-in at the call-protocol level; a caller that does not advance gets a
    frozen mirror, which since 2026-08-01 raises ``MirrorDesync`` rather than silently
    answering for a stale position.

    ``rust_threads`` folds the ``k_dets`` worlds across OS threads (None ⇒ 1). ⚠️ In a
    GAME-PARALLEL FARM this must stay 1: game parallelism owns the cores, and W16 x t8 =
    128 hot threads is the documented failure mode. 1 is the default here for exactly
    that reason; only an interactive/single-game caller should raise it."""
    from .fair_agent import FairHeuristicPriorAgent

    if cfg is None:
        cfg = production_prior_cfg()

    if backend == "auto":
        backend = str(load_production_spec().backend)
    if backend not in KNOWN_BACKENDS:
        raise ValueError(
            f"backend must be one of {sorted(KNOWN_BACKENDS)} (or 'auto'); "
            f"got {backend!r}")
    if rust_threads is not None and backend != "rust":
        raise ValueError(
            f"rust_threads is a backend='rust' knob; got backend={backend!r}")

    if backend == "rust":
        # Gap 3 of the audit: the Rust core carries NO net evaluator and none of the
        # python-only search variants, so anything in this list is not "slower on rust",
        # it is ABSENT. Fail closed rather than silently dropping a knob that changes
        # play (the same failure REVIEW #5 found in the make_production_champion guard).
        _py_only = {
            "net": net, "evaluator": evaluator, "sighted_game": sighted_game,
            "batch_size": batch_size, "batch_evaluator": batch_evaluator,
            "virtual_loss": virtual_loss,
            "oracle_prior_mult": oracle_prior_mult,
            "oracle_prior_eps_coef": oracle_prior_eps_coef,
            "meeple_dedup": meeple_dedup, "intra_reuse": intra_reuse,
            "parallel_workers": parallel_workers,
        }
        _set = sorted(k for k, v in _py_only.items()
                      if v is not _UNSET and v is not None and v is not False)
        if _set:
            raise ValueError(
                f"backend='rust' does not implement {_set}: carc_rs carries no net "
                "evaluator (so --info fair-netprior / fair-net stay python) and none "
                "of the python-only search variants. Use rust_threads for the k_dets "
                "split; parallel_workers is the SPAWN-process one.")
        from .rust_agent import RustFairAgent

        rs_kw = {k: v for k, v in dict(
            sims=sims, k_dets=k_dets, seed=seed, exact_endgame=exact_endgame,
            exact_max_k=exact_max_k, min_pooled_visits=min_pooled_visits,
            exact_budget=exact_budget,
        ).items() if v is not _UNSET}
        if "sims" not in rs_kw or "k_dets" not in rs_kw:
            raise ValueError(
                "backend='rust' needs an explicit sims= and k_dets=: RustFairAgent has "
                "no implicit budget to fall through to (the Python agent's own defaults "
                "are what _UNSET relies on). Pass the harness's resolved budget.")
        # F9 A0 (2026-08-02): the Rust mirror inherits the PYTHON GAME'S geometry.
        # It previously took `window_size`/`start_rule`/`start_row`/`start_col` at
        # their own defaults and this builder passed none of them — fine while the
        # only geometry was the walled one, and a silent python/Rust rules split
        # the moment a profile moves the start tile. Forwarded from `game` (not
        # from the profile) so an explicitly-constructed non-default Game is
        # mirrored too. Inert under `walled`: window_size is already 25, and
        # neither `recentred` nor `fixed_start_tile` is set, so `rs_kw` is
        # byte-identical to what it was before this block.
        rs_kw["window_size"] = int(getattr(game, "window_size", 25))
        if getattr(game, "recentred", False):
            rs_kw["start_row"] = int(game.start_row)
            rs_kw["start_col"] = int(game.start_col)
        if getattr(game, "fixed_start_tile", False):
            rs_kw["start_rule"] = "retail"
        # F9 A2+A3 (2026-08-03, the compose merge): the same argument one line
        # up, for the two RULES flags. Both default to the engine of record, so
        # this stays byte-identical under `walled`; without it a flags-on cell
        # built through this factory would mirror a flags-OFF Rust agent, and
        # `state_digest` does not hash the deck, so the split would only surface
        # plies after the two boards had already parted.
        if getattr(game, "cloister_scan_fix", False):
            rs_kw["cloister_scan_fix"] = True
        _dr = getattr(game, "draw_rule", None)
        if _dr is not None and _dr != "engine":
            rs_kw["draw_rule"] = str(_dr)
        return RustFairAgent(game, cfg, threads=int(rust_threads or 1), **rs_kw)

    kw = {k: v for k, v in dict(
        sims=sims, k_dets=k_dets, seed=seed, exact_endgame=exact_endgame,
        exact_max_k=exact_max_k, min_pooled_visits=min_pooled_visits,
        exact_budget=exact_budget, net=net, evaluator=evaluator,
        sighted_game=sighted_game, batch_size=batch_size,
        batch_evaluator=batch_evaluator, virtual_loss=virtual_loss,
        oracle_prior_mult=oracle_prior_mult,
        oracle_prior_eps_coef=oracle_prior_eps_coef,
        meeple_dedup=meeple_dedup, intra_reuse=intra_reuse,
        parallel_workers=parallel_workers,
    ).items() if v is not _UNSET}
    return FairHeuristicPriorAgent(game, cfg, **kw)


# --------------------------------------------------------------------------- #
# NET-FORWARD BACKEND — which device computes the fair-net-prior candidate's      #
# policy forward. Canonical definition lives in `coreml_evaluator` (a leaf module #
# with no factory dependency); re-exported here so harnesses have ONE public seam #
# and the factory owns the manifest stamp, exactly like exact_budget /            #
# parallel_workers above.                                                         #
# --------------------------------------------------------------------------- #
from .coreml_evaluator import (  # noqa: E402  (kept next to its users)
    DEFAULT_NET_BACKEND,
    NET_BACKENDS,
    resolve_net_backend,
)

__all_net_backend__ = (NET_BACKENDS, DEFAULT_NET_BACKEND, resolve_net_backend)


def net_backend_manifest_block(backend: str, *, model_path=None,
                               model_sha256=None, compute_units=None,
                               source: str = "kwarg") -> dict:
    """The manifest stamp for a non-default net-forward backend.

    Shaped like the ``exact_budget`` / ``parallel_workers`` blocks and stamped on the
    SAME no-hash-drift terms: emitted ONLY when the caller actually bound a backend, so
    a candidate built without the kwarg carries a manifest byte-identical to the
    pre-feature one.

    Unlike ``parallel_workers`` this is NOT behaviour-identical. fp16 on the ANE is a
    different arithmetic from fp32 on CUDA: the priors differ in the last bits and can
    reorder near-ties, so the agent is a genuinely different player and its strength
    claim is its own. That is the whole point of the M5 cell, and it is why the block
    records the artifact hash — a strength number is only interpretable next to the
    exact .mlpackage that produced it.
    """
    return {
        "backend": str(backend),
        "default": DEFAULT_NET_BACKEND,
        "source": source,
        "model_path": None if model_path is None else str(model_path),
        "model_sha256": model_sha256,
        "compute_units": compute_units,
        "scope": "the POLICY forward only. The value stays the frozen champion v2.9 "
                 "leaf, computed in-process by the same Cython float leaf as the "
                 "torch backend — the backend cannot touch it.",
        "mask": "applied HOST-side in float32 (masked_fill(-inf) then softmax), NOT "
                "baked into the CoreML graph, so the only fp16 effect is on the "
                "logits themselves (coreml_evaluator DESIGN DECISION 1).",
        "note": "NOT behaviour-identical to the torch backend — fp16 accelerator "
                "arithmetic perturbs the priors and can reorder near-ties. This agent "
                "is NOT the deployed champion of governance/PRODUCTION.yaml.",
    }


def build_fair_netprior_candidate(game, *, cfg=None, net=None, handles=None,
                                  coreml_model=None, net_backend=None,
                                  sighted_game=None, sighted=None,
                                  sims=_UNSET, k_dets=_UNSET, seed=_UNSET,
                                  exact_endgame=_UNSET, exact_max_k=_UNSET,
                                  min_pooled_visits=_UNSET, exact_budget=_UNSET,
                                  batch_size=_UNSET, batch_evaluator=_UNSET,
                                  virtual_loss=_UNSET):
    """Construct the CL-067 fair-net-prior CANDIDATE: NET policy priors + the FROZEN
    champion v2.9 leaf value, on the chosen forward backend.

    One entry point for the agent the equal-wall-clock gate measured, so the M5/ANE cell
    and the desktop CUDA cell differ in exactly ONE argument (``net_backend``) rather
    than in two hand-assembled construction sites.

    ``net_backend`` follows the ``exact_budget`` / ``parallel_workers`` convention:
    None means "do not pass it at all", i.e. the torch resolution that existed before
    this kwarg — so an unset call is byte-identical and carries no manifest key. When
    it IS set, ``agent.manifest["net_backend"]`` is stamped (see
    ``net_backend_manifest_block``).

    ``cfg=None`` defaults to the production curve125 config — the same leaf the
    candidate's net was distilled against, and the leaf ``_assert_netprior_leaf``
    requires. Everything left at ``_UNSET`` falls through to the agent's own defaults.
    """
    from .heuristic_prior_mcts import make_fair_net_prior_evaluator

    if cfg is None:
        cfg = production_prior_cfg()
    backend = resolve_net_backend(net_backend)

    evaluator = make_fair_net_prior_evaluator(
        cfg, net=net, handles=handles, coreml_model=coreml_model,
        net_backend=net_backend, sighted_game=sighted_game, sighted=sighted)

    agent = build_fair_champion(
        game, cfg=cfg, sims=sims, k_dets=k_dets, seed=seed,
        exact_endgame=exact_endgame, exact_max_k=exact_max_k,
        min_pooled_visits=min_pooled_visits, exact_budget=exact_budget,
        evaluator=evaluator, batch_size=batch_size,
        batch_evaluator=batch_evaluator, virtual_loss=virtual_loss)

    # Provenance the harness manifest reads back off the agent.
    agent.netprior_evaluator = evaluator
    agent.net_backend = backend
    if net_backend is not None:
        agent.manifest = {"net_backend": net_backend_manifest_block(
            backend,
            model_path=getattr(coreml_model, "carc_path", None),
            compute_units=getattr(coreml_model, "carc_compute_units", None),
        )}
    return agent


def build_clairvoyant_champion(game, *, cfg=None, simulations, seed=_UNSET,
                               reuse_tree=_UNSET, meeple_dedup=_UNSET,
                               backend: str = "python", auto_advance: bool = False):
    """Construct the clairvoyant PUCT champion (HeuristicPriorAgent) — the dev/ruler
    agent (reads the true deck). Byte-identical to a direct construction; ``cfg=None``
    defaults to the production curve125 config.

    ``backend="python"`` (the default) is unchanged, byte-for-byte, and is what every
    existing caller gets.

    ``backend="rust"`` (2026-08-02) returns ``rust_agent.RustCarryClairvoyantAgent`` —
    the SAME player on carc_rs, with BOTH of the Python agent's tree policies:
    ``best_action`` carries the tree (never clears, at any ``reuse_tree``) and ``move``
    clears or re-roots.  That distinction is the whole of **Gap 2** of
    BACKEND_BYPASS_AUDIT_20260801 §3, and it is why this builder used to refuse:
    ``MirrorState.search_single`` is fresh-tree only, so a ``best_action``-driven ruler
    (``oracle_score_pilot``'s continuation) would have been a DIFFERENT PLAYER —
    measured in measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json.  Gap 2 is
    closed by ``carc_rs.PersistentSearcher``; Gap 1 (search seed) was closed by
    GAP1_SEED_INVARIANCE.json; **Gap 3 (evaluator injection) is still OPEN and still
    refuses** — see ``RustCarryClairvoyantAgent``.

    ⚠️ THIS IS A REFERENCE INSTRUMENT.  A converted ruler grades nothing until its own
    identity gates are green: ``scripts/rustport/gate_gap2_persistent.py`` (the carried
    continuation) and ``scripts/rustport/gate_clair_backend.py`` (the full-game
    ``--info clair`` leg, per-ply action + root stats).

    ⚠️ MIRROR CONTRACT.  A Rust ruler owns a game mirror: ``start_game(board)`` (or
    ``seat(deck_seed, prefix)``) once, then ``advance()`` for every applied action of
    BOTH seats.  ``auto_advance=True`` is for ``best_action``-driven playout loops that
    own no mirror and apply exactly the action they were handed; it is ignored on the
    python backend, whose agent has no mirror to advance."""
    from .heuristic_prior_mcts import HeuristicPriorAgent

    if backend == "auto":
        backend = str(load_production_spec().backend)
    if backend not in KNOWN_BACKENDS:
        raise ValueError(
            f"backend must be one of {sorted(KNOWN_BACKENDS)} (or 'auto'); "
            f"got {backend!r}")

    if cfg is None:
        cfg = production_prior_cfg()
    kw = {k: v for k, v in dict(seed=seed, reuse_tree=reuse_tree,
                                meeple_dedup=meeple_dedup).items()
          if v is not _UNSET}

    if backend != "python":
        # MEEPLE-DEDUP is a python-only search variant; the Rust core narrows no
        # action set. Refuse rather than silently drop it (the C-g failure mode).
        from . import meeple_equiv

        if meeple_equiv.resolve(None if meeple_dedup is _UNSET else meeple_dedup):
            raise ValueError(
                "meeple_dedup has no carc_rs implementation (the Rust search runs the "
                "raw legal mask); build this ruler with backend='python'.")
        from .rust_agent import RustCarryClairvoyantAgent

        kw.pop("meeple_dedup", None)
        return RustCarryClairvoyantAgent(game, cfg, simulations=int(simulations),
                                         auto_advance=bool(auto_advance), **kw)

    return HeuristicPriorAgent(game, cfg, simulations=int(simulations), **kw)


# --------------------------------------------------------------------------- #
# The high-level entry point                                                    #
# --------------------------------------------------------------------------- #
def make_production_champion(mode: str, *, game=None, seed: int = 0,
                             sims: int | None = None, k_dets: int | None = None,
                             exact_endgame: bool = True, verify: bool = True,
                             meeple_dedup: bool | None = None,
                             intra_reuse: bool | None = None,
                             exact_budget: int | None = None,
                             parallel_workers: int | None = None,
                             backend: str = "python",
                             rust_threads: int | None = None):
    """Instantiate the production champion named by governance/PRODUCTION.yaml and attach
    its resolved runtime manifest (``agent.manifest``). ``verify=True`` PROVES the leaf on
    real boards at construction and RAISES on any mismatch.

    mode="fair"        -> FairHeuristicPriorAgent (deployable PIMC at the YAML budget —
                          k8x1376 = 11008 since the 2026-07-29 promotion — exact-K<=2).
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
    silently doing nothing.

    ``parallel_workers`` splits the fair agent's ``k_dets`` determinization worlds
    across that many SPAWN processes (None = do not pass it at all, i.e. today's
    sequential k-loop — byte-identical to before this kwarg existed, which is what
    the Chaquopy/Android bridge must keep getting since it has no multiprocessing).
    It is BEHAVIOR-IDENTICAL by construction (the worlds are independent until the
    pooled-Q argmax; same decks, same seeds, same merge order — proven in
    tests/test_kparallel.py), so it is a single-GAME LATENCY lever and needs no
    strength re-eval. FAIR MODE ONLY; passing it with mode="clairvoyant" raises.

    ``backend`` selects which ENGINE computes the champion: ``"python"`` (the default),
    ``"rust"`` (``rust_agent.RustFairAgent`` over ``carc_rs``, the rustport P4 core), or
    ``"auto"`` (resolve from ``governance/PRODUCTION.yaml``
    ``champion.fair_deploy.backend``; absent ⇒ python). The Rust backend is
    BEHAVIOR-IDENTICAL BY GATE — G4 reproduced the deployed champion bit-exactly
    (0/305,515 checks) and G6 re-proves it as 100% action agreement over 100 full
    deck-paired games (14,384/14,384) — and the leaf VALUE PANEL is re-verified through
    ``carc_rs`` at construction, so a wrong Rust leaf cannot reach the board. FAIR MODE
    ONLY (there is no clairvoyant Rust agent). ``rust_threads`` splits the ``k_dets``
    worlds across that many OS threads INSIDE one GIL-released call (None = 1, the
    sequential fold); G4 proved the merge bit-identical at threads {1, 4, 8}, so it is a
    latency lever exactly like ``parallel_workers``.

    ⚠️ WHY "auto" EXISTS AND WHY IT IS NOT THE DEFAULT. Since 2026-08-01 the YAML names
    ``backend: rust`` for the desktop profile, but ``RustFairAgent`` is NOT a drop-in for
    the Python champion: it owns a game mirror that advances ONLY on an explicit
    ``advance()`` call, and 5 of this repo's 6 call sites never make one
    (measurement/rustport_p6/BACKEND_BYPASS_AUDIT_20260801.md). Flipping the default
    would hand those callers a mirror frozen at ply 1. So the YAML value is reached only
    by a caller that opts in with ``"auto"``, which is that caller ASSERTING it drives
    the mirror (``start_game()`` once, then ``advance()`` for EVERY applied action of
    BOTH seats). A wrong assertion is no longer silent in either direction:
    ``choose_action`` hard-raises ``MirrorDesync`` on any drift, unconditionally."""
    from . import intra_reuse as intra_carry
    from . import meeple_equiv
    from .game_wrapper import Game

    spec = load_production_spec()
    if game is None:
        game = Game(enable_legal_moves_cache=True)
    leaf_cfg = production_leaf_cfg(spec)
    cfg = production_prior_cfg(spec, leaf_cfg)
    # "auto" = "resolve the engine from governance/PRODUCTION.yaml". It is a SEPARATE
    # value rather than the default because a caller cannot be swapped onto the Rust
    # backend behind its back: `RustFairAgent` owns a mirror that only moves on an
    # explicit `advance()`, and 5 of this repo's 6 call sites never call it
    # (measurement/rustport_p6/BACKEND_BYPASS_AUDIT_20260801.md). Passing "auto" is
    # therefore a caller ASSERTION — "I drive the mirror: start_game() once, advance()
    # for every applied action of BOTH seats". Callers that do not are unaffected,
    # because the default is still "python" and is byte-identical to before this field.
    # A wrong assertion can no longer be silent either way: since 2026-08-01
    # `RustFairAgent.choose_action` hard-raises `MirrorDesync` on drift.
    if backend == "auto":
        backend = str(spec.backend)
    if backend not in KNOWN_BACKENDS:
        raise ValueError(
            f"backend must be one of {sorted(KNOWN_BACKENDS)} (or 'auto'); "
            f"got {backend!r}")
    manifest = resolved_manifest(mode, spec, leaf_cfg, cfg, verify=verify,
                                 backend=backend)

    # Left at _UNSET when the caller said nothing, so the agent constructor is called
    # with EXACTLY the argument list it had before this feature existed.
    dedup_kw = {} if meeple_dedup is None else {"meeple_dedup": bool(meeple_dedup)}
    intra_kw = {} if intra_reuse is None else {"intra_reuse": bool(intra_reuse)}
    budget_kw = {} if exact_budget is None else {"exact_budget": int(exact_budget)}
    par_kw = ({} if parallel_workers is None
              else {"parallel_workers": int(parallel_workers)})
    if parallel_workers is not None and mode != "fair":
        raise ValueError(
            "parallel_workers is a FAIR-mode feature (it splits the PIMC agent's "
            f"k_dets determinization worlds); got mode={mode!r}")
    if intra_reuse is not None and mode != "fair":
        raise ValueError(
            "intra_reuse is a FAIR-mode feature (the within-turn carry needs the PIMC "
            f"agent's tile+meeple decision pair); got mode={mode!r}")
    if exact_budget is not None and mode != "fair":
        raise ValueError(
            "exact_budget is a FAIR-mode feature (only the PIMC agent runs the endgame "
            f"solver); got mode={mode!r}")

    if backend == "rust" and mode != "fair":
        raise ValueError(
            "backend='rust' is a FAIR-mode capability (carc_rs ports the PIMC agent, "
            f"not the clairvoyant ruler); got mode={mode!r}")
    # ⚠️ RESOLVED values, not the raw kwargs (REVIEW 2026-08-02 #5 / ROUND2 F-1).
    # `None` is the INHERIT-FROM-PROCESS sentinel for meeple_dedup and intra_reuse, so
    # the raw-kwarg form of this guard was blind to a variant enabled by
    # CARCASSONNE_MEEPLE_DEDUP / CARCASSONNE_INTRA_TURN_REUSE (or by a runtime
    # `meeple_equiv.set_enabled(True)`). In that state a Rust champion was built with
    # the variant SILENTLY DROPPED — carc_rs implements neither — and then stamped with
    # `manifest["meeple_dedup"] = {"enabled": True}` further down, because THAT branch
    # already consults the env. The manifest claimed a search variant the agent had not
    # run. Resolving here makes the guard and the stamp read the same source.
    _dedup_on = meeple_equiv.resolve(meeple_dedup)
    _intra_on = mode == "fair" and intra_carry.resolve(intra_reuse)
    if backend == "rust" and (_dedup_on or _intra_on or parallel_workers):
        raise ValueError(
            "backend='rust' does not carry the python-only search variants "
            f"(meeple_dedup={_dedup_on} / intra_reuse={_intra_on} — note these "
            "resolve from the environment when the kwarg is None) or the "
            "SPAWN-process split (parallel_workers — use rust_threads, which splits "
            "the same worlds across OS threads inside one GIL-released call)")
    if rust_threads is not None and backend != "rust":
        raise ValueError(
            f"rust_threads is a backend='rust' knob; got backend={backend!r}")

    if backend == "rust":
        from .rust_agent import RustFairAgent

        # ⚠️ THE MIRROR INHERITS THE PYTHON GAME'S GEOMETRY AND RULES FLAGS.
        # This branch forwarded NONE of them until 2026-08-03, while
        # `build_fair_champion`'s rust branch (above) has forwarded geometry
        # since F9 A0 — so a champion built through THIS entry point ran the
        # mirror on walled 35x35/engine-start no matter what Game it was handed.
        # Under `fixed_v1` that is a guaranteed ply-0 desync (python pre-places
        # the retail start tile, the mirror does not), which is how the arm-F
        # launch failed. Same shape as the other branch, and equally inert under
        # `walled`: window_size is already 25 and none of the flags are set.
        _rs_geom: dict = {"window_size": int(getattr(game, "window_size", 25))}
        if getattr(game, "recentred", False):
            _rs_geom["start_row"] = int(game.start_row)
            _rs_geom["start_col"] = int(game.start_col)
        if getattr(game, "fixed_start_tile", False):
            _rs_geom["start_rule"] = "retail"
        if getattr(game, "cloister_scan_fix", False):
            _rs_geom["cloister_scan_fix"] = True
        _dr = getattr(game, "draw_rule", None)
        if _dr is not None and _dr != "engine":
            _rs_geom["draw_rule"] = str(_dr)
        agent = RustFairAgent(
            game, cfg,
            sims=(spec.sims_per_det if sims is None else int(sims)),
            k_dets=(spec.k_dets if k_dets is None else int(k_dets)),
            seed=int(seed), exact_endgame=bool(exact_endgame),
            exact_max_k=spec.exact_max_k,
            threads=(1 if rust_threads is None else int(rust_threads)),
            **_rs_geom, **budget_kw)
    elif mode == "fair":
        agent = build_fair_champion(
            game, cfg=cfg,
            sims=(spec.sims_per_det if sims is None else int(sims)),
            k_dets=(spec.k_dets if k_dets is None else int(k_dets)),
            seed=int(seed), exact_endgame=bool(exact_endgame),
            exact_max_k=spec.exact_max_k, **dedup_kw, **intra_kw, **budget_kw,
            **par_kw)
    elif mode == "clairvoyant":
        total = (spec.k_dets * spec.sims_per_det) if sims is None else int(sims)
        agent = build_clairvoyant_champion(
            game, cfg=cfg, simulations=total, seed=int(seed), **dedup_kw)
    else:
        raise ValueError(f"mode must be 'fair'|'clairvoyant'; got {mode!r}")

    # The manifest's fair_deploy block records the PRODUCTION.yaml INTENT (the champion of
    # record). If sims/k_dets override it — a smoke, OR a deploy PROFILE that cannot pay the
    # champion budget, e.g. the Android `mobile` profile — record the budget the agent
    # ACTUALLY runs, so the game log never misrepresents what played. resolved_manifest
    # itself stays canonical/byte-stable (the note is added only on the attached copy).
    if mode == "fair":
        es = spec.sims_per_det if sims is None else int(sims)
        ek = spec.k_dets if k_dets is None else int(k_dets)
        if (es, ek) != (spec.sims_per_det, spec.k_dets):
            manifest = dict(manifest)
            manifest["runtime_budget_override"] = {
                "sims_per_det": es, "k_dets": ek, "total_sims": es * ek,
                "note": "the budget the agent ACTUALLY runs; fair_deploy above is the "
                        "PRODUCTION.yaml intent (the champion of record). A budget BELOW "
                        "the intent is a WEAKER agent and must be graded as such."}
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

    # k-PARALLEL: stamped ONLY when the caller actually asked for the split, on the
    # same no-hash-drift terms as the kwargs above. Stamped even though the split is
    # behavior-IDENTICAL, so a game log records which execution mode produced it (a
    # latency claim is only interpretable next to the worker count).
    if parallel_workers is not None:
        manifest = dict(manifest)
        manifest["parallel_workers"] = {
            "workers": int(parallel_workers),
            "source": "kwarg",
            "scope": "execution only — the k_dets determinization worlds run on "
                     "min(workers, k_dets) spawn processes and are merged by the "
                     "SAME pooled-Q code path, in the same world order",
            "note": "BEHAVIOR-IDENTICAL (same decks, same per-world seeds, same "
                    "merge order — tests/test_kparallel.py). A single-GAME latency "
                    "lever; it does NOT change play and needs no strength re-eval.",
        }

    # rust-THREADS: the backend='rust' twin of parallel_workers, stamped on the same
    # no-hash-drift terms (only when the caller actually asked for a split).
    if rust_threads is not None:
        manifest = dict(manifest)
        manifest["rust_threads"] = {
            "threads": int(rust_threads),
            "source": "kwarg",
            "scope": "execution only — the k_dets determinization worlds run on "
                     "min(threads, k_dets) OS threads inside ONE GIL-released "
                     "choose_action call and are merged by the same pooled-Q fold, "
                     "in the same world order",
            "note": "BEHAVIOR-IDENTICAL (rustport G4 proved threads {1,4,8} "
                    "bit-identical). A single-GAME latency lever.",
        }

    agent.manifest = manifest
    return agent
