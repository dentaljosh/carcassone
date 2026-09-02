"""Desktop adapter for the Rust fair champion (`carc_rs.FairAgentRs`) — rustport P6.

ONE object that presents the Rust k-parallel PIMC agent through the surface the
Python fair champion already exposes to its callers, so a harness can swap
backends without learning a second shape:

    agent = RustFairAgent(game, cfg, sims=1376, k_dets=8, seed=101)
    agent.start_game(board)                 # seat the mirror on the real deck
    while not game.get_game_ended(board, 0):
        a = agent.choose_action(board) if my_turn else opponent.move(board)
        board, _ = game.get_next_state(board, a)
        agent.advance(a)                    # EVERY applied action, BOTH seats

WHY A MIRROR AT ALL.  The Rust core owns its own game state (the FFI contract is
"mirror state advanced by action ints" — build spec §Architecture); the Python
engine stays authoritative for UI / legality / save.  That is two copies of the
same game, and two copies drift.  Three things keep them honest:

  1. **A single choke point.**  `advance()` is the ONLY way the mirror moves, and
     it must be called for every applied action of BOTH seats.  There is no
     "sync from a board" path, because the Rust state cannot be constructed from
     an arbitrary position — only replayed — so a silent resync is impossible by
     construction and a desync can only ever be an error.
  2. **`start_game(board)` reads the REAL deck** out of the caller's initial
     board (`[next_tile] + deck` in draw order) rather than re-deriving it from
     an RNG seed.  The adapter therefore never assumes how the caller seeded
     `random`, and works for the phone/save path where there is no seed at all.
  3. **Reconcile mode** (`CARC_RS_RECONCILE=1`): every decision hard-asserts the
     mirror's `string_repr()` against `game.string_representation(board)` — the
     byte-equal node key G1 gated — and raises `MirrorDesync`.  Drift can never
     be silent.  It costs one repr per own-move, so it is a gate/CI mode, not a
     production one.

COUNTERS.  `stats()` carries BOTH shapes the eval harness reads:

  * the AGENT shape (`fair_agent.FairHeuristicPriorAgent`): `heur_moves`,
    `exact_moves`, `n_timeouts`, `solver_secs`, `solver_nodes`, `max_solve_secs`,
    `latch_k`, `last_pooled_visits`, `neural_moves` (always 0, harness symmetry);
  * the HARNESS-WRAPPER shape (`eval_fair_puct._MarginalizedHandoff`):
    `prefix_moves` / `prefix_secs` — the search-only clock that feeds
    `champ_prefix_ms_per_move`.

`prefix_secs` is computed TRUTHFULLY, not copied: the wall clock is taken around
the FFI call (so it includes the FFI hop the caller actually pays) and the
solver's own time — measured inside Rust, the same `solver_secs` accumulator the
Python agent keeps — is subtracted.  A latched decision that the solver owned
contributes ZERO prefix time and does not increment `prefix_moves`, exactly as
`_MarginalizedHandoff` does; a `BudgetExceeded` decision contributes its PIMC
fallback to the prefix and its dead solve to `solver_secs`, again exactly as the
Python path does.

STATUS (2026-08-01).  `governance/PRODUCTION.yaml` now names `fair_deploy.backend:
rust` — this engine is the champion's execution backend OF RECORD, on G4/G6
evidence (bit-exact reproduction; 14,384/14,384 identical actions over 100 full
games).  `champion_factory.make_production_champion` nevertheless STILL DEFAULTS
to `backend="python"`, and that is deliberate, not a leftover: the mirror
contract above means this class is not a drop-in.  A caller reaches the YAML
value by passing `backend="auto"`, which is that caller asserting it calls
`start_game()` once and `advance()` for every applied action of both seats.  Five
of this repo's six call sites do neither (measurement/rustport_p6/
BACKEND_BYPASS_AUDIT_20260801.md), which is why the resolution is opt-in and why
`choose_action` now hard-raises `MirrorDesync` on drift unconditionally rather
than only under `CARC_RS_RECONCILE`.
"""
from __future__ import annotations

import os
import time

# The panel `champion_factory._LEAF_VALUE_PANEL` pins, evaluated through carc_rs.
# Kept here (not in the factory) so the factory keeps ONE import of this module.
RECONCILE_ENV = "CARC_RS_RECONCILE"


class MirrorDesync(RuntimeError):
    """The Rust mirror and the Python board disagree. Never recoverable."""


def reconcile_enabled(explicit: bool | None = None) -> bool:
    """Resolve reconcile mode: explicit kwarg wins, else ``CARC_RS_RECONCILE=1``."""
    if explicit is not None:
        return bool(explicit)
    return os.environ.get(RECONCILE_ENV, "0") == "1"


# --------------------------------------------------------------------------- #
# Config translation — Python LeafConfig / HeuristicPriorConfig -> carc_rs      #
# --------------------------------------------------------------------------- #
def leaf_config_rs(leaf_cfg):
    """`carcassonne_ai.virtual_score_v2.LeafConfig` -> ``carc_rs.LeafConfigRs``.

    Field-for-field, with `closure_p` sorted by open-count — the same mapping
    `scripts/rustport/reconcile_leaf._to_rs` drove through all 12 config dialects
    of G2 (3,341,772 bit-exact leaf values). Kept in src/ so a production caller
    never has to import a gate script."""
    import carc_rs

    curve = leaf_cfg.v29_meeple_curve
    # Targeted denial: forwarded as KEYWORDS, and ONLY when the dose is set. A
    # carc_rs build that predates the denial term then keeps serving every
    # default-off (champion) config unchanged, while a NONZERO dose against the
    # stale build raises TypeError — fail-closed loud, never a silently-intact
    # leaf (the F7b dropped-kwarg hazard, test_leaf_config_rs_forwards_*).
    denial = {}
    if float(getattr(leaf_cfg, "denial_dose", 0.0)) != 0.0:
        denial = dict(
            denial_dose=float(leaf_cfg.denial_dose),
            denial_size_min=float(leaf_cfg.denial_size_min),
            denial_open_max=int(leaf_cfg.denial_open_max),
        )
    # Open-city discipline: same conditional-keyword rule as targeted denial above —
    # a carc_rs build predating the term keeps serving every default-off (champion)
    # config unchanged, while a NONZERO dose against the stale build raises TypeError
    # (fail-closed loud, never a silently-intact leaf).
    opencity = {}
    if float(getattr(leaf_cfg, "opencity_dose", 0.0)) != 0.0:
        opencity = dict(
            opencity_dose=float(leaf_cfg.opencity_dose),
            opencity_size_min=float(leaf_cfg.opencity_size_min),
            opencity_edge_min=int(leaf_cfg.opencity_edge_min),
            opencity_symmetric=bool(leaf_cfg.opencity_symmetric),
        )
        # opencity_cap (2026-08-14) is NESTED-conditional: an opencity-capable but
        # cap-stale carc_rs build keeps serving every UNCAPPED cell unchanged, while
        # a nonzero cap against the stale build raises TypeError (fail-closed loud,
        # never a silently-uncapped leaf — which would re-run CL-080's arm, not the
        # capped candidate).
        if float(getattr(leaf_cfg, "opencity_cap", 0.0)) != 0.0:
            opencity["opencity_cap"] = float(leaf_cfg.opencity_cap)
    # J-rules on search: same conditional-keyword rule as targeted denial / open-city
    # above — a carc_rs build predating the bundle keeps serving every default-off
    # (champion) config unchanged, while a NONZERO dose against the stale build raises
    # TypeError (fail-closed loud, never a silently-J-rule-free leaf, which would read
    # as "the anchor's strategy is worth nothing" instead of "it never ran").
    jrules = {}
    if float(getattr(leaf_cfg, "jrules_dose", 0.0)) != 0.0:
        jrules = dict(
            jrules_dose=float(leaf_cfg.jrules_dose),
            jrules_mask=int(leaf_cfg.jrules_mask),
        )
    # Tile-tie tie-break: same conditional-keyword rule as denial / open-city /
    # jrules above. ⚠️ There is NO rust mirror of this term yet (deliberately
    # deferred — see measurement/tiletie_term_20260814/DESIGN.md), so TODAY a
    # NONZERO dose against ANY carc_rs build raises TypeError (fail-closed loud,
    # never a silently tiebreak-blind leaf). Default-off (champion) configs are
    # served unchanged. When the mirror lands, this forwarding is already correct.
    tiletie = {}
    if float(getattr(leaf_cfg, "tiletie_dose", 0.0)) != 0.0:
        tiletie = dict(
            tiletie_dose=float(leaf_cfg.tiletie_dose),
            tiletie_w_city=float(leaf_cfg.tiletie_w_city),
            tiletie_w_road=float(leaf_cfg.tiletie_w_road),
            tiletie_w_perim=float(leaf_cfg.tiletie_w_perim),
            tiletie_w_lib=float(leaf_cfg.tiletie_w_lib),
            tiletie_norm=float(leaf_cfg.tiletie_norm),
        )
    # Invasion-risk family (shapes A/B/C/D; spec
    # measurement/invasion_term_build/SHAPES.md): same conditional-keyword rule as
    # denial / open-city / jrules / tiletie above. A carc_rs build predating the
    # family keeps serving every default-off (champion) config unchanged, while a
    # NONZERO weight against the stale build raises TypeError (fail-closed loud,
    # never a silently invasion-blind leaf, which would read as "the term is worth
    # nothing" instead of "the term never ran").
    # ⚠️ THIS IS THE ONE FAMILY THAT EXISTS ONLY IN RUST — the Python leaves RAISE on
    # a nonzero weight, so `--backend rust` is not a speed preference here, it is the
    # only route.
    # The two INERT shape-B knobs are NESTED-conditional on `invasion_alpha` (the
    # opencity_cap pattern): an invasion-capable build that predates a later knob
    # keeps serving every default cell, and a moved knob against it fails closed.
    invasion = {}
    if (float(getattr(leaf_cfg, "invasion_beta", 0.0)) != 0.0
            or float(getattr(leaf_cfg, "invasion_alpha", 0.0)) != 0.0
            or float(getattr(leaf_cfg, "invasion_gamma", 0.0)) != 0.0
            or float(getattr(leaf_cfg, "invasion_delta_farm", 0.0)) != 0.0):
        invasion = dict(
            invasion_beta=float(getattr(leaf_cfg, "invasion_beta", 0.0)),
            invasion_alpha=float(getattr(leaf_cfg, "invasion_alpha", 0.0)),
            invasion_gamma=float(getattr(leaf_cfg, "invasion_gamma", 0.0)),
            invasion_delta_farm=float(getattr(leaf_cfg, "invasion_delta_farm", 0.0)),
        )
        if float(getattr(leaf_cfg, "invasion_alpha", 0.0)) != 0.0:
            if float(getattr(leaf_cfg, "invasion_alpha_cap", 0.0)) != 0.0:
                invasion["invasion_alpha_cap"] = float(leaf_cfg.invasion_alpha_cap)
            if int(getattr(leaf_cfg, "invasion_stub_max_tiles", 2)) != 2:
                invasion["invasion_stub_max_tiles"] = int(leaf_cfg.invasion_stub_max_tiles)
    return carc_rs.LeafConfigRs(
        sorted((int(k), float(v)) for k, v in leaf_cfg.closure_p.items()),
        float(leaf_cfg.bonus_cap),
        float(leaf_cfg.opp_bonus_cap),
        float(leaf_cfg.meeple_k),
        [float(x) for x in curve] if curve else None,
        float(getattr(leaf_cfg, "soft_cap_slope", 0.0)),
        float(getattr(leaf_cfg, "opp_soft_cap_slope", 0.0)),
        float(leaf_cfg.v29_meeple_return_k),
        float(leaf_cfg.v29_farm_flip_k),
        bool(getattr(leaf_cfg, "bag_close", False)),
        bool(leaf_cfg.tile_counting_closure),
        float(leaf_cfg.closure_continuous_slack),
        bool(getattr(leaf_cfg, "farm_base_off", False)),
        bool(getattr(leaf_cfg, "farm_growth_off", False)),
        float(getattr(leaf_cfg, "v29_phase_beta", 0.0)),
        float(getattr(leaf_cfg, "v29_phase_norm", 1.0)),
        **denial,
        **opencity,
        **jrules,
        **tiletie,
        **invasion,
    )


def search_config_rs(cfg, sims: int):
    """`HeuristicPriorConfig` + a sim budget -> ``carc_rs.SearchConfigRs``.

    `exp_fma=True` / `tanh_flavor="glibc_fma"` are the G0 findings for x86-64
    desktop (`np.exp` float64 == glibc `__exp_fma`; `math.tanh` likewise); they
    are what makes the Rust priors bit-identical here.

    ⛔⛔ `fpu_reduction` is now FORWARDED from `cfg`, not hard-coded (the
    2026-08-29 false-negative audit; `measurement/fpu_resurrection_prep`). Until
    that date this slot carried a LITERAL `None`, so the CHAMPION COULD NOT
    EXPRESS THE KNOB AT ALL: `carc_rs` had accepted `Option<f64>` since the
    rustport and `carc_core::search` implemented it (`mod.rs:816`), but no
    `HeuristicPriorConfig` value could reach it, and the only leaf-value FPU
    cells ever measured (`experiments/results.csv` rows 68-69, +45.4 / +31.4
    elo at n=200, 2026-06-02) were therefore never confirmable on the backend
    the champion plays on. **This is the same silent-divergence failure `c_lcb`
    was fixed for below, one surface over** — and it was WORSE, because a
    caller that set `fpu_reduction` got a config whose python leg honoured it
    (`mcts.py:1225`) and whose Rust leg did not, i.e. two DIFFERENT agents
    wearing one config.

    ⭐ `None` remains the default and remains the champion, bit-for-bit: it is
    the NeuralMCTS legacy optimistic `q = 0` for unvisited children, and it is
    what keeps the Rust priors bit-identical here. ⚠️ `None` and `0.0` are NOT
    the same request — `Some(0.0)` takes the `node_q - 0.0` branch (the
    PARENT's Q), not zero — so the value is passed through without coercion.
    The bit-exact-when-None property is the round's GOLDEN GATE
    (`measurement/fpu_resurrection_prep/selftest_fixture/`), and no rust change
    was needed or made, so the wheel does not move across this fix.

    ⚠️ `c_lcb` is now FORWARDED from `cfg`, not hard-coded (ROUND2 C-g). It is
    inert while `final_select` is "Q"/"visits", which is why the hard-coded 1.0
    survived every gate — but a caller that sets `final_select="lcb"` with a
    tuned `c_lcb` got the Rust leg silently scoring at 1.0, i.e. a DIFFERENT
    selection rule than the Python leg it was being compared against.

    `root_select` / `gumbel_*` have NO Rust implementation at all. Rather than
    drop them (the same silent-divergence failure), anything other than the
    "puct" default RAISES here — the caller keeps `backend="python"`."""
    import carc_rs

    from .game_wrapper import SCORE_NORM_SCALE

    root_select = str(getattr(cfg, "root_select", "puct"))
    if root_select != "puct":
        raise ValueError(
            f"root_select={root_select!r} has no carc_rs implementation (the Rust "
            "core runs PUCT root selection only); Gumbel-root / sequential-halving "
            "is a python-only search variant. Build this agent with "
            "backend='python'.")
    # Gumbel knobs are only READ when root_select == "gumbel", so a non-default
    # value here is inert — but it signals a caller that believes it configured
    # something, and silence is what C-g is about. Checked against the dataclass
    # defaults so a config that merely carries them is not rejected.
    _gumbel_defaults = {"gumbel_m": 16, "gumbel_c_visit": 50.0,
                        "gumbel_c_scale": 1.0, "gumbel_retain_g": True}
    _off_default = [k for k, v in _gumbel_defaults.items()
                    if getattr(cfg, k, v) != v]
    if _off_default:
        raise ValueError(
            f"gumbel knobs {sorted(_off_default)} are set on a config bound for the "
            "Rust backend, which implements no Gumbel root. They would be silently "
            "dropped; build this agent with backend='python'.")

    # J-RULES PRIOR surface B (search-level knobs, NOT leaf fields): forwarded
    # as KEYWORDS, and ONLY when the dose is set — the same conditional-keyword
    # rule as the denial/open-city/jrules LEAF knobs in `leaf_config_rs` above.
    # A `carc_rs` build predating surface B keeps serving every default-off
    # (champion) config unchanged, while a NONZERO dose against the stale build
    # raises TypeError (fail-closed loud, never a silently prior-free search,
    # which would read as "the anchor's strategy is worth nothing" instead of
    # "it never ran").
    jrules_prior = {}
    if float(getattr(cfg, "jrules_prior_dose", 0.0)) != 0.0:
        jrules_prior = dict(
            jrules_prior_dose=float(cfg.jrules_prior_dose),
            jrules_prior_mask=int(getattr(cfg, "jrules_prior_mask", 31)),
            jrules_prior_scope=str(getattr(cfg, "jrules_prior_scope", "all")),
        )
    # J-RULES ROOT FILTER surface C: same conditional-keyword rule. A carc_rs
    # build predating surface C keeps serving every default-off (champion)
    # config unchanged, while a NONZERO mask against the stale build raises
    # TypeError (fail-closed loud, never a silently filter-free search, which
    # would read as "the anchor's hard rules change nothing" instead of "they
    # never ran").
    jrules_filter = {}
    if int(getattr(cfg, "jrules_filter_mask", 0)) != 0:
        jrules_filter = dict(
            jrules_filter_mask=int(cfg.jrules_filter_mask),
            jrules_filter_min_keep=int(getattr(cfg, "jrules_filter_min_keep", 1)),
        )
    # TIE ARBITER (tiearb2 Stage 2 Phase B): same conditional-keyword rule. A
    # carc_rs build predating the arbiter keeps serving every default-off
    # (champion) config unchanged, while an ENABLED arbiter against the stale
    # build raises TypeError — fail-closed loud, never a silently arbiter-free
    # candidate, which would read as "terminal grounding at ties is worth
    # nothing in games" instead of "it never ran". That is exactly the J13
    # failure mode this surface is built to refuse.
    tiearb = {}
    if bool(getattr(cfg, "tiearb_enabled", False)):
        tiearb = dict(
            tiearb_enabled=True,
            tiearb_b=int(getattr(cfg, "tiearb_b", 16)),
            tiearb_j=int(getattr(cfg, "tiearb_j", 4)),
            tiearb_mode=str(getattr(cfg, "tiearb_mode", "argmax")),
            tiearb_salt=str(getattr(cfg, "tiearb_salt", "tiearb2-deploy-v1")),
            tiearb_eps=float(getattr(cfg, "tiearb_eps", 0.0)),
            # THE PHASE FIRE-GATE (measurement/phasegate_prep). Passed ONLY
            # inside the already-conditional ENABLED block, so the same
            # fail-closed rule the whole surface follows extends to it: a wheel
            # predating the gate serves every default-off (champion) config
            # unchanged, while an ENABLED arbiter raises TypeError instead of
            # silently running UNGATED — which on an ARB_EARLY cell would
            # produce a perfectly healthy-looking duplicate of ARB_FULL.
            tiearb_phase_gate=str(getattr(cfg, "tiearb_phase_gate", "all")),
        )
    # ⭐⭐ RISK-ASYMMETRIC WORLD POOLING — GT-M1 (measurement/cvar_pool_prep).
    # SAME conditional-keyword rule, and it exists for the SAME reason the FPU
    # docstring above records at length: THIS FUNCTION IS WHERE KNOBS GO MISSING.
    # `fpu_reduction` sat here as a hard-coded `None` for months while both legs
    # claimed to implement it, and the only cells ever measured on the axis were
    # unconfirmable. So this surface is forwarded from `cfg`, never defaulted at
    # this seam, and `tests/test_cvar_pool_knob.py` asserts the RESOLVED rust
    # config carries it rather than asserting the source text mentions it.
    #
    # A carc_rs build predating GT-M1 keeps serving every default-`mean`
    # (champion) config unchanged — the keys are simply not passed — while a
    # `cvar` request against that stale wheel raises TypeError: fail-closed loud,
    # never a silently mean-pooled candidate, which would read as "risk-averse
    # pooling is worth nothing" instead of "it never ran".
    pool = {}
    if str(getattr(cfg, "pool_mode", "mean")) != "mean":
        pool = dict(
            pool_mode=str(cfg.pool_mode),
            # ⛔ NOT coerced to a default. `HeuristicPriorConfig.__post_init__`
            # already refused `cvar` without an alpha, and `PoolMode::parse`
            # refuses it again on the rust side; if it is somehow None here the
            # rust layer must be the one to say so.
            pool_alpha=(None if getattr(cfg, "pool_alpha", None) is None
                        else float(cfg.pool_alpha)),
        )
    # ⚠️ `resolved_leaf_cfg()`, NOT `cfg.leaf_cfg` (fixed 2026-08-02). `leaf_cfg=None`
    # is the SENTINEL for "the env-built DEFAULT_CONFIG", and it is what every caller
    # that relies on the leaf env rather than an explicit override passes — including
    # `gen_fair_distill._champion_cfg`. Reading the raw attribute crashed there with
    # `NoneType has no attribute v29_meeple_curve`. The champion_factory path never hit
    # it because `production_prior_cfg` always injects an explicit curve125 LeafConfig.
    return carc_rs.SearchConfigRs(
        leaf_config_rs(cfg.resolved_leaf_cfg() if hasattr(cfg, "resolved_leaf_cfg")
                       else cfg.leaf_cfg),
        int(sims),
        float(cfg.c_puct),
        float(cfg.tau_p),
        float(cfg.value_norm),
        float(SCORE_NORM_SCALE),
        str(cfg.leaf_quantize),
        str(cfg.final_select),
        # ⛔ THE FORWARDED FPU (was a hard-coded None until 2026-08-29 — see the
        # docstring). `getattr` default None keeps every config predating the
        # field working, and `None` stays `None` rather than becoming `0.0`.
        (None if getattr(cfg, "fpu_reduction", None) is None
         else float(cfg.fpu_reduction)),
        float(getattr(cfg, "c_lcb", 1.0)),
        True,
        "glibc_fma",
        **jrules_prior,
        **jrules_filter,
        **tiearb,
        **pool,
    )


def leaf_value_panel_rs(leaf_cfg) -> dict:
    """`champion_factory._leaf_value_panel`, evaluated by the RUST leaf.

    The factory's deepest guard is a panel of leaf OUTPUTS on canonical boards.
    When the champion runs on the Rust backend those outputs are produced by
    `carc_core::leaf`, so the guard has to be evaluated THERE or it proves
    nothing about the agent that will actually play. `MirrorState.
    make_empty_panel_state` builds the identical board the Python panel does
    (empty 35x35, no meeples placed, scores 0, no next tile, hand counts set)."""
    import carc_rs

    from .champion_factory import _LEAF_VALUE_PANEL

    rcfg = leaf_config_rs(leaf_cfg)
    ms = carc_rs.MirrorState.from_seed("0")
    out = {}
    for label, (meeples, kind, _golden) in _LEAF_VALUE_PANEL.items():
        ms.make_empty_panel_state(int(meeples[0]), int(meeples[1]))
        out[label] = (float(ms.leaf_value_float(0, rcfg)) if kind == "float"
                      else int(ms.leaf_value(0, rcfg)))
    return out


def _code_rev_reported() -> str:
    from .run_manifest import code_rev

    return code_rev()


def carc_rs_binary_sha() -> str:
    """sha256[:16] of the INSTALLED `carc_rs` extension binary.

    ⚠️ **BOX-LOCAL, and NOT comparable across machines.** Two boxes that compile
    the identical source with the identical toolchain produce different bytes
    (embedded paths, host CPU feature selection); measured 2026-08-17 —
    local `73aa20102ab98e2f` vs laptop `ec140ac0c0583d53` at the same commit and
    the same `rustc 1.96.0`. Use it to prove a wheel was REBUILT on this box (its
    value moves when the source moves), never to prove two boxes agree.
    """
    import hashlib
    from pathlib import Path

    import carc_rs

    try:
        pkg = Path(carc_rs.__file__).parent
        blobs = sorted(p for p in pkg.iterdir()
                       if p.suffix in (".so", ".pyd", ".dylib"))
        if not blobs:
            return "nobinary"
        h = hashlib.sha256()
        for b in blobs:
            h.update(b.name.encode())
            h.update(b.read_bytes())
        return h.hexdigest()[:16]
    except Exception:                                       # noqa: BLE001
        return "unhashed"


def carc_rs_build_id() -> str:
    """The CROSS-BOX-COMPARABLE build identity — the `G-TOOL` witness
    (`measurement/tiearb2_stage2_20260817/READ_RULE.md` §3, "the two boxes did
    not run the same rust toolchain / the same `carc_rs` build").

    `carc_rs-<cargo version>+<repo rev>+rustc<toolchain>`.

    ⚠️ Why NOT the binary hash. A `G-TOOL` gate is an EQUALITY check between two
    boxes' stamps, and the compiled `.so` is not reproducible across machines
    (see [`carc_rs_binary_sha`]) — a hash-based id would fail that gate on every
    healthy 2-box run. The three components here DO move together with the code
    and the compiler and DO compare across boxes. The box-local staleness
    question is answered separately, by `carc_rs_binary_sha` plus the per-host
    positive control, which is the only thing that can prove the installed wheel
    actually carries the surface under test.
    """
    import carc_rs

    from .run_manifest import code_rev

    tc = os.environ.get("RUSTUP_TOOLCHAIN") or "unpinned"
    # ⚠️ The FULL commit, sliced to a FIXED 12 — not `code_rev()`'s output.
    # `code_rev()` uses `git rev-parse --short`, whose length is `core.abbrev`
    # and therefore PER BOX: measured 2026-08-17, the same commit rendered
    # `cf51bf17` locally and `cf51bf176b` on the laptop. A `G-TOOL` equality gate
    # would have failed on identical code because the two boxes abbreviate
    # differently. The "-dirty" suffix is dropped for the same class of reason:
    # two boxes at the same commit can carry different uncommitted files (a live
    # tree with a concurrent session in it), and dirtiness must not void a gate
    # it is not evidence about — it is reported as its own field instead.
    rev = "unknown"
    try:
        import subprocess
        from pathlib import Path as _P
        out = subprocess.run(
            ["git", "-C", str(_P(__file__).resolve().parents[2]), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            rev = out.stdout.strip()[:12]
    except Exception:                                       # noqa: BLE001
        rev = code_rev().replace("-dirty", "")
    return f"carc_rs-{carc_rs.__version__}+{rev}+rustc{tc}"


def backend_provenance() -> dict:
    """Which carc_rs build is executing — the Rust half of the fingerprint guard."""
    import carc_rs

    tiles_src, tiles_sem = carc_rs.tile_data_digests()
    return {
        "carc_rs_version": str(carc_rs.__version__),
        "carc_rs_path": str(carc_rs.__file__),
        # The `G-TOOL` mixed-build witness, and it is CROSS-BOX COMPARABLE
        # (cargo version + repo rev + rustc toolchain) — unlike the Cargo
        # version alone, which never moves, and unlike the binary hash below,
        # which is not reproducible across machines.
        "carc_rs_build": carc_rs_build_id(),
        # BOX-LOCAL staleness evidence. Do NOT compare it across boxes.
        "carc_rs_binary_sha": carc_rs_binary_sha(),
        "code_rev": _code_rev_reported(),
        "code_rev_dirty": _code_rev_reported().endswith("-dirty"),
        "rust_toolchain": os.environ.get("RUSTUP_TOOLCHAIN"),
        "tile_data_source_sha256": tiles_src,
        "tile_data_semantic_digest": tiles_sem,
    }


# --------------------------------------------------------------------------- #
# Net-arm seam (probe only — no net arm runs on the Rust backend yet)           #
# --------------------------------------------------------------------------- #

# The CL-067 equal-wall-clock gate's reopen bar, restated device-independently:
# REOPEN the distilled-net line for deploy when the target device's measured
# `r = forward_ms / search_ms_per_sim` is <= ~1.5.
# Canonical statement: measurement/classical_search/NETPRIOR_EQTIME_GATE_20260728.md §6.
NET_ARM_REOPEN_R_BAR = 1.5


def net_arm_backend_status() -> dict:
    """Can a NET arm (`fair-net`, `fair-netprior`) run on the Rust backend? — probe.

    Today the answer is **no**, and this function exists so callers ask instead of
    assuming. `champion_factory` / `eval_fair_puct.py` route the net arms to Python
    unconditionally; that routing is correct but it is currently implicit, so a
    reader cannot tell "net arms are Python" from "net arms happen to be Python
    here". A probe that returns `supported=False` with a reason is the difference
    between a documented constraint and an accident.

    It also carries the two numbers a caller needs to reason about the trade,
    because they are counter-intuitive in the Rust era:

    * `reopen_r_bar` — the gate's bar, unchanged.
    * `r_is_an_upper_bound` — **the port inverts how `r` should be read.** `r`
      models the forward as purely ADDITIVE on top of an unchanged search. For
      `fair-netprior` that is wrong: net priors REPLACE the classical evaluator's
      child-leaf sweep (`1 + |legal|` leaf calls per expansion, measured ~9.6 leaf
      evals per simulation by `carc-core`'s `examples/evalprobe.rs`), so the arm
      deletes work as well as adding it. In Python the distinction did not matter —
      a 4.2 ms forward dwarfed everything it displaced. In Rust the displaced sweep
      is a large fraction of per-simulation cost, so `r` OVERSTATES the true cost
      ratio and the decision-bearing quantity is the measured per-move cost ratio.

    See `docs/RUST_NET_EVAL_DESIGN_20260802.md` for the backend comparison, the
    measured `r` ladder, and the acceptance tiers a backend must clear.

    Returns a dict; never raises, so it is safe in a manifest-stamping path.
    """
    try:
        import carc_rs
        have_module = True
        version = str(carc_rs.__version__)
        # The PyO3 surface a wired net arm would need. Absent by design today: the
        # prototype evaluator lives in the `carc-net` crate, which is an excluded
        # workspace and is not linked into `carc_rs`.
        has_evaluator = hasattr(carc_rs, "PolicyEvaluatorRs")
    except Exception as exc:  # pragma: no cover - carc_rs absent is a valid state
        have_module = False
        version = None
        has_evaluator = False
        reason = f"carc_rs not importable: {exc}"
    else:
        reason = (
            "carc_rs exposes no PolicyEvaluatorRs; the net-arm seam "
            "(carc_core::eval::PolicyEvaluator) has a prototype backend in the "
            "carc-net crate but is not wired into the PyO3 module or into search"
        )

    return {
        "supported": bool(have_module and has_evaluator),
        "reason": None if (have_module and has_evaluator) else reason,
        "carc_rs_present": have_module,
        "carc_rs_version": version,
        "reopen_r_bar": NET_ARM_REOPEN_R_BAR,
        "r_is_an_upper_bound": True,
        "design_doc": "docs/RUST_NET_EVAL_DESIGN_20260802.md",
    }


# --------------------------------------------------------------------------- #
# The adapter                                                                  #
# --------------------------------------------------------------------------- #
def _draw_order_for_mirror(st, mirror_preplaces: bool) -> list[str]:
    """The ORIGINAL draw order of `st`'s deck, as the Rust mirror must receive it.

    ⚠️ THIS IS NOT SIMPLY ``[next_tile] + deck``, and the difference is a real
    bug that reached a Phase-B launch (F9 `fixed_v1`, arm F, died at ply 0 with
    python tiles-remaining 70 vs rust 69).

    `start_game_from_deck` does not import a finished state — it hands the deck
    to ``Game::from_deck_with_config``, which then runs the mirror's OWN setup
    under the SAME `GameConfig` the agent was built with. Under
    ``start_rule="retail"`` that setup pre-places the start tile, and it takes
    the tile by *removing the first entry whose description matches* from
    ``[next_tile] + deck``.

    But the Python board handed to us has ALREADY been through exactly that
    step: `game_wrapper.preplace_retail_start_tile` removed the first matching
    `city_top_straight_road` from its own pool and put it on the board. So the
    deck we can observe is the POST-setup one. Hand that over and the Rust side
    removes a *second* copy — the base deck holds four — and the two engines
    part company on deck length at ply 0. `next_tile` still agrees whenever the
    duplicate sits later in the pool, which is why the symptom is a lone
    tiles-remaining digest field and not an obviously wrong board.

    The inverse is exact rather than heuristic. Python removed the FIRST match,
    so re-inserting the pre-placed tile at index 0 yields a pool whose first
    match IS that tile; Rust's identical "remove the first match" rule then
    removes index 0 and reproduces the observed deck, in order, byte for byte.

    ⚠️ It takes BOTH sides to decide this, which is the second half of the same
    bug. `mirror_preplaces` is the mirror's own resolved `start_rule`, and the
    board's `placed_coords` is what Python actually did. Keying off only ONE of
    them is wrong in a way that still looks like a deck bug:

      * board pre-placed + mirror pre-places  -> prepend (the case above);
      * board pre-placed + mirror does NOT    -> the mirror was built on walled
        geometry while the Game is retail. Prepending here would leave the tile
        sitting unplayed at the head of the mirror's deck (71 remaining vs 70,
        the MIRROR IMAGE of the original symptom). That is a construction bug in
        the caller, so it RAISES rather than being papered over;
      * board virgin + mirror pre-places      -> the mirror would invent a
        placement the Python board never made. Also raises.
    """
    descs = [st.next_tile.description] + [t.description for t in st.deck]
    placed = list(st.placed_coords)
    if not placed:
        if mirror_preplaces:
            raise RuntimeError(
                "the Rust mirror is configured start_rule='retail' but the Python "
                "board has no pre-placed start tile: the mirror would place a tile "
                "this game never dealt. Build the agent from the same Game the "
                "board came from (champion_factory forwards the geometry).")
        return descs                      # engine start rule — nothing pre-placed
    if not mirror_preplaces:
        raise RuntimeError(
            "the Python board has a pre-placed retail start tile but the Rust "
            "mirror is configured start_rule='engine': the mirror cannot "
            "reproduce this setup and would run one tile behind for the whole "
            "game. The agent must be built with start_rule='retail' (and the "
            "matching start_row/start_col) — see champion_factory's rust branch.")
    if len(placed) != 1:
        raise RuntimeError(
            f"start_game cannot seat a mirror on a board with {len(placed)} "
            "pre-placed tiles: the draw order that produced them is not "
            "recoverable. Only the retail single-start-tile setup is supported.")
    c = placed[0]
    tile = st.get_tile(c.row, c.column)
    if tile is None:                      # unreachable; refuse rather than guess
        raise RuntimeError(f"placed_coords lists {c!r} but the board cell is empty")
    return [tile.description] + descs


def mirror_geometry_kwargs(game) -> dict:
    """The RULES kwargs a Rust mirror must be built with to mirror `game`.

    F9-A0 hole, closed 2026-08-03 (the caps/curve re-sweep build). The rules
    profile reaches `game_wrapper.Game` through `rules_profile.active()`, and
    `champion_factory`'s rust branch already forwarded the resolved geometry to
    `RustFairAgent` — but the two CLAIRVOYANT adapters below built their mirrors
    with a bare `MirrorState.from_deck(descs)`, i.e. always on the ENGINE OF
    RECORD, whatever `--rules-profile` said. Measured under `fixed_v1`: the
    Python board carries the retail start tile at (18,15) and the Rust mirror is
    an empty engine6 board at ply 0 — and `_check_sync` is gated on
    `CARC_RS_RECONCILE` (default OFF), so a `--backend rust --rules-profile
    fixed_v1` eval would have graded two agents reading a different game from
    the referee, silently.

    Deriving the kwargs FROM THE GAME (rather than re-reading the profile) is
    deliberate: the mirror's contract is with the `Game` object it is handed, so
    an explicitly-constructed `Game(draw_rule=...)` is honoured too, and a
    caller that builds the agent from a different Game than the board came from
    still trips `_draw_order_for_mirror`'s pre-placement refusals.

    DEFAULT-OFF: under `walled` every test below is False/engine, so this
    returns `{}` minus the always-default `window_size`, and the FFI call is the
    one it always made. Mirrors champion_factory's rust branch field for field.
    """
    kw: dict = {}
    if getattr(game, "recentred", False):
        kw["start_row"] = int(game.start_row)
        kw["start_col"] = int(game.start_col)
    if getattr(game, "fixed_start_tile", False):
        kw["start_rule"] = "retail"
    if getattr(game, "cloister_scan_fix", False):
        kw["cloister_scan_fix"] = True
    _dr = getattr(game, "draw_rule", None)
    if _dr is not None and str(_dr) != "engine":
        kw["draw_rule"] = str(_dr)
    return kw


def _resolve_mirror_window(game, window_size: int) -> int:
    """The window the mirror must run: `game`'s, and it may not be contradicted.

    Before 2026-08-03 the clairvoyant adapters stored `window_size` and never
    passed it to the FFI, so a caller's value was silently dead. Now that it is
    live, "the game quietly wins" would be a second silent class — the mirror
    cannot be on a different window from the board it is digest-checked against.
    No caller in the tree passes this argument, so the raise is a contract
    statement, not a migration.
    """
    gw = getattr(game, "window_size", None)
    if gw is None:
        return int(window_size)
    if int(window_size) != int(gw):
        raise ValueError(
            f"window_size={window_size} contradicts the Game's window_size={gw}; "
            "the mirror must run the window of the board it mirrors. Build the "
            "agent from the Game the board came from, or drop the argument.")
    return int(gw)


class RustFairAgent:
    """`carc_rs.FairAgentRs` behind the `FairHeuristicPriorAgent` surface.

    Construction mirrors `champion_factory.build_fair_champion`: the caller
    hands the same `game` and `HeuristicPriorConfig` it would hand the Python
    agent, and every knob that changes PLAY (`sims`, `k_dets`, `seed`,
    `exact_endgame`, `exact_max_k`, `min_pooled_visits`, `exact_budget`) has the
    same meaning and the same default. `threads` is the ONE extra knob, and it
    is execution-only: G4 proved the merge bit-identical at threads {1, 4, 8}.
    """

    # Harness symmetry with the Python agent (`neural_moves` is always 0 there).
    neural_moves = 0

    def __init__(self, game, cfg, *, sims: int, k_dets: int, seed: int = 0,
                 exact_endgame: bool = True, exact_max_k: int | None = None,
                 min_pooled_visits: float | None = None,
                 exact_budget: int | None = None, threads: int = 1,
                 window_size: int = 25, start_rule: str | None = None,
                 start_row: int | None = None, start_col: int | None = None,
                 cloister_scan_fix: bool | None = None,
                 draw_rule: str | None = None,
                 reconcile: bool | None = None,
                 sims_tile: int | None = None,
                 sims_meeple: int | None = None,
                 exact_objective: str = "margin",
                 wc_tiebreak: bool = False):
        import carc_rs

        from . import fair_agent as _fa

        self._game = game
        self._cfg = cfg
        self._sims = int(sims)
        self._k_dets = int(k_dets)
        self._seed = int(seed)
        self._threads = int(threads)
        # --- SIMS-SPLIT (phase-asymmetric sims budget; None/None = byte-identical).
        # Same contract as FairHeuristicPriorAgent's sims_tile/sims_meeple: the named
        # phase's PIMC decisions run each world at that budget, None inherits `sims`.
        # Implemented as a PER-CALL `sims_override` on FairAgentRs.choose_action —
        # stateless on the Rust side (the constructed SearchConfigRs is never
        # mutated), so it cannot desync the mirror protocol or leak across
        # `reset()`/games. Phase detection uses the PYTHON board handed to
        # choose_action (`board.state.phase`) — the same phase notion the python
        # agent uses — and `check_sync` has already hard-asserted that board equals
        # the mirror before the override is applied.
        if sims_tile is not None and int(sims_tile) < 1:
            raise ValueError(f"sims_tile must be >= 1 (or None), got {sims_tile}")
        if sims_meeple is not None and int(sims_meeple) < 1:
            raise ValueError(f"sims_meeple must be >= 1 (or None), got {sims_meeple}")
        self._sims_tile = None if sims_tile is None else int(sims_tile)
        self._sims_meeple = None if sims_meeple is None else int(sims_meeple)
        self.sims_tile = self._sims_tile       # public alias (manifest read-off)
        self.sims_meeple = self._sims_meeple   # public alias (manifest read-off)
        self._reconcile = reconcile_enabled(reconcile)
        # Does the MIRROR run the retail pre-placement? `start_game` needs this
        # to reconstruct the pre-setup draw order (see _draw_order_for_mirror);
        # `None` == "engine" == the engine of record, matching the FFI default.
        self._mirror_preplaces = (start_rule == "retail")
        # Defaults READ from fair_agent (point-don't-copy), so the adapter can
        # never quote a budget the Python champion has since moved off.
        self._exact_max_k = int(_fa.EXACT_MAX_K if exact_max_k is None else exact_max_k)
        self._min_pooled_visits = float(
            _fa.DEFAULT_MIN_POOLED_VISITS if min_pooled_visits is None
            else min_pooled_visits)
        self._exact_budget = int(
            _fa.DEFAULT_EXACT_BUDGET if exact_budget is None else exact_budget)
        self._exact_endgame = bool(exact_endgame)
        # E1: the exact solver's objective (SOLVER-side; the leaf hash does not
        # move — surface-B liveness convention). The FFI kwarg is only passed
        # when non-default, so (a) the default construction is byte-for-byte
        # the pre-knob FFI call and (b) an OLD carc_rs wheel keeps working at
        # "margin" — while a "win" request on an old wheel fails LOUDLY below
        # (TypeError from the binding) instead of silently playing margin.
        # ⚠️ Per-box footgun: carc_rs is a BUILT wheel; rebuild it on every box
        # before any run that passes exact_objective="win".
        if exact_objective not in ("margin", "win"):
            raise ValueError(
                f"exact_objective must be 'margin'|'win', got {exact_objective!r}")
        self._exact_objective = str(exact_objective)
        self.exact_objective = self._exact_objective   # public alias (manifest read-off)
        # WC tie-break (BACKLOG 2026-08-03 "WC tie-break rule flag"). Rule of the
        # MATCH, not a candidate-side knob: it applies symmetrically to both
        # agents and keys off SEAT (seat 0 = starting player). Default False ->
        # byte-identical FFI call (the kwarg is only passed when non-default,
        # same idiom as exact_objective above). ⚠️ Per-box footgun: carc_rs is a
        # BUILT wheel; rebuild it on every box before any run that passes
        # wc_tiebreak=True.
        self._wc_tiebreak = bool(wc_tiebreak)
        self.wc_tiebreak = self._wc_tiebreak   # public alias (manifest read-off)

        try:
            _obj_kw = ({} if self._exact_objective == "margin"
                       else {"exact_objective": self._exact_objective})
            _wc_kw = {} if not self._wc_tiebreak else {"wc_tiebreak": self._wc_tiebreak}
            self._rs = carc_rs.FairAgentRs(
                search_config_rs(cfg, self._sims),
                k_dets=self._k_dets,
                seed=self._seed,
                min_pooled_visits=self._min_pooled_visits,
                exact_endgame=self._exact_endgame,
                exact_max_k=self._exact_max_k,
                exact_budget=self._exact_budget,
                tt_cap=0,
                chance_drop="type",
                threads=self._threads,
                **_obj_kw,
                **_wc_kw,
                window_size=int(window_size),
                start_rule=start_rule,
                start_row=start_row,
                start_col=start_col,
                # F9/A2, threaded at the A2+A3 compose merge (2026-08-03) for the
                # SAME reason A3 gives below: the A2 branch closed this hole for
                # `draw_rule` only, so a `--backend rust` A2 cell would have run the
                # DRIFTING scan on the Rust side while Python ran the fix. `None`
                # == False == the engine of record, so the default path is untouched.
                cloister_scan_fix=cloister_scan_fix,
                # F9/A3. `None` == "engine" == the engine of record, so the default
                # path is untouched. It MUST be threaded rather than left to the
                # Rust default: `start_game` hands over the deck and the Rust side
                # then rolls the game forward on its OWN engine, so a mirror on the
                # other draw rule would place different tiles from the first
                # unplaceable draw onward — and `state_digest` (which does not hash
                # the deck) would only catch it once the boards had already parted.
                draw_rule=draw_rule,
            )
        except TypeError as e:
            if "exact_objective" in str(e):
                raise RuntimeError(
                    "this carc_rs wheel predates the E1 exact_objective knob — "
                    "rebuild the wheel on THIS box (per-box footgun: carc_rs is a "
                    "built artifact) before running exact_objective="
                    f"{self._exact_objective!r}") from e
            if "wc_tiebreak" in str(e):
                raise RuntimeError(
                    "this carc_rs wheel predates the WC tie-break wc_tiebreak knob "
                    "— rebuild the wheel on THIS box (per-box footgun: carc_rs is a "
                    "built artifact; reinstall from rust/carc/target/wheels) before "
                    "running wc_tiebreak="
                    f"{self._wc_tiebreak!r}") from e
            raise
        self._started = False
        self._plies = 0
        # The harness-wrapper clock (`_MarginalizedHandoff`), computed here.
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        self.total_secs = 0.0
        self.manifest: dict | None = None

    # --- lifecycle ---------------------------------------------------------- #
    def start_game(self, board) -> None:
        """Seat the mirror on the deck THIS board was dealt.

        `[next_tile] + deck` is the engine's draw order (`get_init_board` pops
        the first tile into `next_tile`), so it reconstructs the game exactly —
        with no dependence on how the caller seeded `random`. Under reconcile
        mode the seated mirror is immediately digest-checked against `board`
        (and `tests/rustport/test_p6_backend.py` pins it equal to what
        `start_game_from_seed` produces for the same deck)."""
        st = board.state
        if st.next_tile is None:
            raise ValueError("start_game needs an INITIAL board (next_tile is None)")
        if self._plies:
            raise RuntimeError(
                "start_game after the mirror has advanced — build a fresh agent "
                "(or call start_game before the first advance)")
        descs = _draw_order_for_mirror(st, self._mirror_preplaces)
        self._rs.start_game_from_deck(descs)
        self._started = True
        self._plies = 0
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        self.total_secs = 0.0
        self._check_sync(board, "start_game")

    def start_game_from_seed(self, deck_seed: int | str) -> None:
        """`random.seed(deck_seed); Game().get_init_board()` — the farms/tests path."""
        self._rs.start_game_from_seed(str(deck_seed))
        self._started = True
        self._plies = 0
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        self.total_secs = 0.0

    def close(self) -> None:
        """No-op — the Rust agent owns no processes (the Python k-parallel
        champion's spawn pool is what `close()` exists for there). Present so
        the adapter is drop-in for `contextlib.closing`-style callers."""

    def __del__(self):                      # pragma: no cover - teardown
        try:
            self.close()
        except Exception:
            pass

    # --- the single mirror choke point -------------------------------------- #
    def advance(self, action: int, board_after=None) -> None:
        """Apply ONE action to the mirror. Call for EVERY applied action, BOTH seats.

        `board_after` is optional and only read in reconcile mode, where it is
        asserted equal to the post-action mirror."""
        if not self._started:
            raise RuntimeError("advance before start_game()")
        self._rs.advance(int(action))
        self._plies += 1
        if board_after is not None:
            self._check_sync(board_after, f"advance({action})")

    # --- the decision ------------------------------------------------------- #
    def choose_action(self, board, move_idx: int | None = None) -> int:
        """Pick the fair move for `board`. Never mutates the caller's board.

        The mirror must already BE at `board` (see `advance`). `move_idx`
        defaults to the agent's own counter, which always advances — the same
        contract `FairHeuristicPriorAgent._move_idx` has."""
        if not self._started:
            # A caller that only ever calls choose_action/advance still gets a
            # correctly seated mirror instead of a RuntimeError.
            self.start_game(board)
        # ⚠️ UNCONDITIONAL, NOT reconcile-gated (2026-08-01). This used to be
        # `self._check_sync(...)`, i.e. a no-op unless CARC_RS_RECONCILE=1 — which
        # made the single most dangerous failure mode of this adapter SILENT: a
        # caller that never calls `advance()` keeps a mirror frozen at its first
        # decision and is handed a move computed for a position the game left long
        # ago, with no error anywhere. Measured: a naive caller re-returns its ply-1
        # action, which is then merely "illegal" if you are lucky and legal-but-wrong
        # if you are not. Five of the six `make_production_champion` call sites in
        # this repo were such callers (BACKEND_BYPASS_AUDIT_20260801.md), so the
        # check has to be free-standing rather than something a gate opts into.
        # COST: 12.8 us per decision on the 5900XT at a midgame board (python
        # `string_representation` ~0.1 us memoised + rust `string_repr` 12.6 us)
        # against a 266 ms k8x1376 t8 decision = 0.005%. There is no budget argument
        # for leaving a correctness guard off at that price.
        # `_check_sync` stays for `advance(board_after=...)`, which is the caller's
        # opt-in per-ply audit and IS the expensive one (a repr per applied action).
        self.check_sync(board, "choose_action")
        # SIMS-SPLIT: resolve THIS decision's per-world budget from the python
        # board's phase (the sync assert one line up has proven board == mirror).
        # None (both knobs unset, or the set knob not naming this phase) is the
        # constructed budget — the pre-knob call, byte for byte.
        sims_override = None
        if self._sims_tile is not None or self._sims_meeple is not None:
            from wingedsheep.carcassonne.objects.game_phase import GamePhase

            sims_override = (self._sims_tile
                             if board.state.phase == GamePhase.TILES
                             else self._sims_meeple)
        solver_before = float(self._rs.stats()["solver_secs"])
        t0 = time.perf_counter()
        action = int(self._rs.choose_action(
            None if move_idx is None else int(move_idx), sims_override))
        dt = time.perf_counter() - t0
        self.total_secs += dt
        m = self._rs.last_move()
        # The `_MarginalizedHandoff` split: a decision the SOLVER owned costs no
        # prefix time and is not a prefix move; anything else ran a PIMC search
        # (including the BudgetExceeded fallback, whose dead solve is subtracted).
        if not bool(m["exact"]):
            solver_delta = float(self._rs.stats()["solver_secs"]) - solver_before
            self.prefix_secs += max(0.0, dt - solver_delta)
            self.prefix_moves += 1
        return action

    move = choose_action

    # --- reconcile ---------------------------------------------------------- #
    def _check_sync(self, board, where: str) -> None:
        if not self._reconcile:
            return
        self.check_sync(board, where)

    def check_sync(self, board, where: str = "check_sync") -> None:
        """Hard-assert the mirror equals `board`, unconditionally.

        Compares the byte-exact `string_representation` — the node key G1 gated,
        which encodes board, phase, scores, meeples, next tile and the last tile
        action. A digest is compared too so the failure message can say WHICH."""
        want = self._game.string_representation(board)
        got = self._rs.string_repr()
        if want == got:
            return
        raise MirrorDesync(
            f"rust mirror desync at {where} (ply {self._plies}, "
            f"move_idx {self.move_idx}): python digest "
            f"{_short(want)} != rust digest {_short(got)}\n"
            f"  python: {want[:400]}\n"
            f"  rust  : {got[:400]}")

    # --- read-off ----------------------------------------------------------- #
    @property
    def move_idx(self) -> int:
        return int(self._rs.stats()["move_idx"])

    @property
    def _move_idx(self) -> int:
        """`FairHeuristicPriorAgent._move_idx` — the same counter, same name."""
        return self.move_idx

    @_move_idx.setter
    def _move_idx(self, value: int) -> None:
        # Seatable, like the Python attribute: a harness that drops the agent
        # onto a recorded ply owns the move timeline (and the det seeds derive
        # from it), so it must be able to say which move this is.
        self._rs.set_move_idx(int(value))

    @property
    def _latched(self) -> bool:
        return bool(self._rs.stats()["latched"])

    @_latched.setter
    def _latched(self, value: bool) -> None:
        # The latch is a function of the game's HISTORY, so a harness that jumps
        # the agent onto a mid-game position via advance() alone — never running
        # choose_action, hence never evaluating the trigger — must seat it.
        self._rs.set_latched(bool(value), self._rs.stats()["latch_k"])

    @property
    def latch_k(self):
        return self._rs.stats()["latch_k"]

    @latch_k.setter
    def latch_k(self, value) -> None:
        self._rs.set_latched(bool(self._rs.stats()["latched"]),
                             None if value is None else int(value))

    @property
    def heur_moves(self) -> int:
        return int(self._rs.stats()["heur_moves"])

    @property
    def forced_moves(self) -> int:
        return int(self._rs.stats()["forced_moves"])

    @property
    def exact_moves(self) -> int:
        return int(self._rs.stats()["exact_moves"])

    @property
    def n_timeouts(self) -> int:
        return int(self._rs.stats()["n_timeouts"])

    @property
    def solver_secs(self) -> float:
        return float(self._rs.stats()["solver_secs"])

    @property
    def solver_nodes(self) -> int:
        return int(self._rs.stats()["solver_nodes"])

    @property
    def max_solve_secs(self) -> float:
        return float(self._rs.stats()["max_solve_secs"])

    @property
    def last_pooled_visits(self) -> dict:
        """`{action: visits}` in POOL INSERTION order (dicts keep it)."""
        return {int(a): float(v) for a, v in self._rs.stats()["last_pooled_visits"]}

    def det_seed_base(self, move_idx: int) -> int:
        return int(self._rs.det_seed_base(int(move_idx)))

    def det_search_seed(self, move_idx: int, det_idx: int) -> int:
        return int(self._rs.det_search_seed(int(move_idx), int(det_idx)))

    def last_move(self) -> dict:
        """The last decision's raw record (pooled floats as raw f64 BITS)."""
        return dict(self._rs.last_move())

    def string_repr(self) -> str:
        return self._rs.string_repr()

    def state_digest(self) -> str:
        return self._rs.state_digest()

    def stats(self) -> dict:
        """Every counter the eval harness reads, in BOTH shapes.

        Agent shape (`FairHeuristicPriorAgent`) and wrapper shape
        (`eval_fair_puct._MarginalizedHandoff`: `prefix_moves`/`prefix_secs`),
        plus the resolved config so a manifest never has to guess which budget
        and which execution mode produced a number."""
        s = self._rs.stats()
        return {
            # --- FairHeuristicPriorAgent ---
            "neural_moves": 0,
            "heur_moves": int(s["heur_moves"]),
            "forced_moves": int(s["forced_moves"]),
            "exact_moves": int(s["exact_moves"]),
            "n_timeouts": int(s["n_timeouts"]),
            "solver_secs": float(s["solver_secs"]),
            "solver_nodes": int(s["solver_nodes"]),
            "max_solve_secs": float(s["max_solve_secs"]),
            "latched": bool(s["latched"]),
            "latch_k": s["latch_k"],
            "move_idx": int(s["move_idx"]),
            "last_pooled_visits": self.last_pooled_visits,
            # --- _MarginalizedHandoff (the champ_prefix_ms_per_move clock) ---
            "prefix_moves": int(self.prefix_moves),
            "prefix_secs": float(self.prefix_secs),
            "total_secs": float(self.total_secs),
            "ms_per_move": (1e3 * self.total_secs / self.move_idx
                            if self.move_idx else 0.0),
            # --- resolved config ---
            "backend": "rust",
            "sims_per_det": int(s["sims_per_det"]),
            "k_dets": int(s["k_dets"]),
            "threads": int(s["threads"]),
            "seed": int(s["seed"]),
            "exact_max_k": int(s["exact_max_k"]),
            "exact_budget": int(s["exact_budget"]),
            "min_pooled_visits": float(s["min_pooled_visits"]),
            "reconcile": bool(self._reconcile),
            "plies_advanced": int(self._plies),
            # SIMS-SPLIT — stamped ONLY when a knob is set, so a knobs-unset
            # stats dict is byte-identical to the pre-feature one.
            **({"sims_tile": self._sims_tile, "sims_meeple": self._sims_meeple}
               if (self._sims_tile is not None or self._sims_meeple is not None)
               else {}),
            # E1 — stamped ONLY when non-default (same convention as above);
            # the RESOLVED value from the rust side when the wheel carries it,
            # so a manifest can never quote a knob the FFI silently dropped.
            **({"exact_objective": str(s.get("exact_objective",
                                            self._exact_objective))}
               if self._exact_objective != "margin" else {}),
            # WC tie-break — stamped ONLY when non-default (same convention as
            # exact_objective above); the RESOLVED value from the rust side when
            # the wheel carries it, so a manifest can never quote a knob the FFI
            # silently dropped.
            **({"wc_tiebreak": bool(s.get("wc_tiebreak", self._wc_tiebreak))}
               if self._wc_tiebreak else {}),
        }

    def __repr__(self) -> str:
        return (f"RustFairAgent(k{self._k_dets}x{self._sims}, seed={self._seed}, "
                f"threads={self._threads}, exact_max_k={self._exact_max_k}, "
                f"reconcile={self._reconcile})")


def _short(s: str) -> str:
    import hashlib

    return hashlib.sha256(s.encode()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# CLASS B — the clairvoyant / instrument tier                                   #
# --------------------------------------------------------------------------- #
class RustClairvoyantAgent:
    """`HeuristicPriorAgent` (the true-deck ruler) on the Rust single-world search.

    The clairvoyant agent is NOT the PIMC champion: it descends the REAL deck
    (`fair_chance=False`) with one tree, no determinizations and no pooling. On the
    Rust side that is exactly `MirrorState.search_single`, whose own docstring pins
    it as *"equivalent to `HeuristicPriorAgent(game, cfg, sims).move(board)` with
    `reuse_tree=False`"*, driven over a mirror seated on the true deck.

    ⚠️ THIS IS A RULER. Converting an instrument changes the instrument, so nothing
    here licenses grading with it — a converted ruler needs its own identity gate on
    the G6 pattern (100% action agreement) before it prices anything. The gate for
    this class is `scripts/rustport/gate_clairvoyant.py`.

    THE THREE GAPS of BACKEND_BYPASS_AUDIT_20260801 §3, and where they now stand:

      * Gap 1 (no search seed on `SearchConfigRs`) — **CLOSED 2026-08-02** by
        `scripts/rustport/gap1_seed_invariance.py`: 75 cross-seed comparisons over 15
        recorded-champion roots at the production per-world budget, bit-identical
        chosen action and root N/W at every seed including `None`. The seed feeds
        `NeuralMCTS._np_rng`, consumed only by temperature sampling and Dirichlet root
        noise, neither engaged under `best_action`. `seed` is therefore accepted and
        recorded here but is genuinely inert; a caller passing one is not lied to.
      * Gap 2 (no `reuse_tree`) — **OPEN, and enforced**: `search_single` is
        fresh-tree only, so `reuse_tree=True` RAISES rather than silently running a
        different search. Inert for the champion (fresh trees per determinization),
        but a ruler that sets it would not be reproducible.
      * Gap 3 (no evaluator injection) — **OPEN, and enforced**: the Rust core carries
        no net, so an injected evaluator RAISES.

    Same mirror contract as `RustFairAgent`: `start_game()` once, then `advance()`
    for every applied action of BOTH seats, and `choose_action` hard-checks sync.
    """

    neural_moves = 0

    def __init__(self, game, cfg, *, simulations: int, seed: int | None = None,
                 reuse_tree: bool = False, evaluator=None,
                 window_size: int = 25, reconcile: bool | None = None):
        import carc_rs

        if reuse_tree:
            raise ValueError(
                "reuse_tree has no carc_rs implementation (MirrorState.search_single "
                "is fresh-tree only — Gap 2 of BACKEND_BYPASS_AUDIT_20260801 §3). "
                "Build this ruler on the python backend.")
        if evaluator is not None:
            raise ValueError(
                "evaluator injection has no carc_rs implementation (the Rust core "
                "carries no net — Gap 3). Build this ruler on the python backend.")
        self._game = game
        self._cfg = cfg
        self._sims = int(simulations)
        # Recorded for the manifest and accepted for signature parity, but PROVEN
        # inert at these knobs (Gap 1 above) — not silently dropped.
        self._seed = seed
        self._reconcile = reconcile_enabled(reconcile)
        self._scfg = search_config_rs(cfg, self._sims)
        self._ms = None
        self._carc_rs = carc_rs
        self._window_size = _resolve_mirror_window(game, window_size)
        # F9-A0: the mirror must run `game`'s RULES, not the engine of record.
        # `{}` under `walled`, so the default FFI call is unchanged.
        self._geom = mirror_geometry_kwargs(game)
        self._mirror_preplaces = (self._geom.get("start_rule") == "retail")
        self._started = False
        self._plies = 0
        self._moves = 0
        self.total_secs = 0.0
        self.prefix_moves = 0
        self.prefix_secs = 0.0

    # --- lifecycle ---------------------------------------------------------- #
    def start_game(self, board) -> None:
        """Seat the mirror on the deck THIS board was dealt (draw order)."""
        st = board.state
        if st.next_tile is None:
            raise ValueError("start_game needs an INITIAL board (next_tile is None)")
        descs = _draw_order_for_mirror(st, self._mirror_preplaces)
        self._ms = self._carc_rs.MirrorState.from_deck(
            descs, window_size=self._window_size, **self._geom)
        self._started = True
        self._plies = self._moves = 0
        self.total_secs = self.prefix_secs = 0.0
        self.prefix_moves = 0
        # UNCONDITIONAL at ply 0 (F9-A0, 2026-08-03): one digest per GAME is free
        # and it is the only cheap place a rules mismatch is guaranteed visible.
        # `_check_sync` (reconcile-gated) stays the per-ply policy.
        self.check_sync(board, "start_game")

    def start_game_from_seed(self, deck_seed: int | str) -> None:
        self._ms = self._carc_rs.MirrorState.from_seed(
            str(deck_seed), window_size=self._window_size, **self._geom)
        self._started = True
        self._plies = self._moves = 0
        self.total_secs = self.prefix_secs = 0.0
        self.prefix_moves = 0

    def close(self) -> None:
        """No-op — the Rust ruler owns no processes. Present for drop-in parity."""

    # --- the single mirror choke point -------------------------------------- #
    def advance(self, action: int, board_after=None) -> None:
        if not self._started:
            raise RuntimeError("advance before start_game()")
        self._ms.advance(int(action))
        self._plies += 1
        if board_after is not None:
            self._check_sync(board_after, f"advance({action})")

    # --- the decision ------------------------------------------------------- #
    def choose_action(self, board) -> int:
        """Pick the clairvoyant move for `board`. Never mutates the caller's board."""
        if not self._started:
            self.start_game(board)
        # Unconditional, for the same reason RustFairAgent's is: a caller that forgets
        # to advance would otherwise be answered from a frozen mirror, silently.
        self.check_sync(board, "choose_action")
        t0 = time.perf_counter()
        res = self._ms.search_single(self._scfg)
        dt = time.perf_counter() - t0
        self.total_secs += dt
        self.prefix_secs += dt
        self.prefix_moves += 1
        self._moves += 1
        self._last = res
        return int(res["chosen_action"])

    move = choose_action
    best_action = choose_action

    # --- reconcile ---------------------------------------------------------- #
    def _check_sync(self, board, where: str) -> None:
        if not self._reconcile:
            return
        self.check_sync(board, where)

    def check_sync(self, board, where: str = "check_sync") -> None:
        want = self._game.string_representation(board)
        got = self._ms.string_repr()
        if want == got:
            return
        raise MirrorDesync(
            f"rust clairvoyant mirror desync at {where} (ply {self._plies}): "
            f"python digest {_short(want)} != rust digest {_short(got)}\n"
            f"  python: {want[:400]}\n  rust  : {got[:400]}")

    # --- read-off ----------------------------------------------------------- #
    def mirror(self):
        """The live `MirrorState`, for callers that need a NON-search Rust surface.

        Added for the F13 exact-K tail (scripts/classical_search/exact_tail.py), which
        runs `MirrorState.solve_endgame` on the position this agent is already
        mirroring rather than standing up a second, independently-seated mirror that
        could drift. READ-ONLY by contract: `solve_endgame` takes `&self`, and callers
        must NOT `advance()` through this handle — the mirror protocol's single choke
        point stays `advance()` on the agent, driven by the harness for BOTH seats."""
        if self._ms is None:
            raise RuntimeError("mirror() before start_game()")
        return self._ms

    def last_search(self) -> dict:
        """The last search's raw surface (floats as raw f64 BITS) — the G3 shape."""
        return dict(self._last)

    def string_repr(self) -> str:
        return self._ms.string_repr()

    def stats(self) -> dict:
        return {
            "backend": "rust",
            "agent_class": "RustClairvoyantAgent",
            "neural_moves": 0,
            "moves": int(self._moves),
            "prefix_moves": int(self.prefix_moves),
            "prefix_secs": float(self.prefix_secs),
            "total_secs": float(self.total_secs),
            "ms_per_move": (1e3 * self.total_secs / self._moves
                            if self._moves else 0.0),
            "simulations": int(self._sims),
            "seed": self._seed,
            "seed_note": "inert at these knobs — proven by "
                         "measurement/rustport_p6/GAP1_SEED_INVARIANCE.json",
            "reuse_tree": False,
            "reconcile": bool(self._reconcile),
            "plies_advanced": int(self._plies),
        }

    def __repr__(self) -> str:
        return (f"RustClairvoyantAgent(sims={self._sims}, seed={self._seed}, "
                f"reconcile={self._reconcile})")


# --------------------------------------------------------------------------- #
# CLASS B, Gap 2 — the PERSISTING-TREE ruler                                    #
# --------------------------------------------------------------------------- #
class RustCarryClairvoyantAgent:
    """`HeuristicPriorAgent` with **both** of its tree policies, on carc_rs.

    ⚠️ READ THIS BEFORE PICKING BETWEEN THIS CLASS AND ``RustClairvoyantAgent``.
    The Python ruler has TWO search semantics and the difference is not cosmetic:

        agent.best_action(board)   ->  mcts.search(board)          # NO clear(), EVER
        agent.move(board)          ->  clear() or _reroot_or_clear # THEN best_action

    ``best_action`` does not clear at any ``reuse_tree`` — the guard is on
    ``move``, and it cannot be keyed off ``cfg.reuse_tree`` because ``best_action``
    never reads it.  So a caller that drives an advancing game through
    ``best_action`` (``oracle_score_pilot._playout_value`` does, every ply to
    terminal) runs ONE transposition table across the whole playout, and each
    ply's root arrives carrying the visits it accumulated as a DESCENDANT of the
    previous ply's tree.  Measured, not inferred:
    ``measurement/rustport_p6/GAP2_ORACLE_CONTINUATION_TREE.json`` — the root
    pre-exists with ``N > sims`` on 102/103 plies, and a fresh-tree replay of the
    identical world diverges in 4/4 positions (terminal margins up to 12 pts
    apart).  ``RustClairvoyantAgent`` aliases ``best_action`` to a FRESH search,
    so it is the right class for a ``.move()``-driven harness and the WRONG one
    for a ``.best_action()``-driven one.  This class implements the distinction.

    It is backed by ``carc_rs.PersistentSearcher``, whose tree outlives the call:

        best_action  -> PersistentSearcher.search()          (carry)
        move         -> .search_fresh()   if not reuse_tree  (clear, then search)
                     -> .search_reroot()  if reuse_tree      (_reroot_or_clear)

    ⚠️ STILL A RULER.  Converting an instrument changes the instrument; this
    class prices nothing until its gates are green
    (``scripts/rustport/gate_gap2_persistent.py``, ``gate_oracle_pilot_backend.py``,
    ``gate_clair_backend.py``).

    MIRROR CONTRACT (the same one ``RustFairAgent`` / ``RustClairvoyantAgent``
    document): seat once, then ``advance()`` EVERY applied action of BOTH seats.
    ``auto_advance=True`` is the exception for ``best_action``-driven playout
    loops, which own no mirror and apply exactly the action they were handed —
    there the agent steps its own mirror.  Either way every decision hard-checks
    sync against the caller's board, so a protocol mistake raises instead of
    silently answering for a stale position.
    """

    neural_moves = 0

    def __init__(self, game, cfg, *, simulations: int, seed: int | None = None,
                 reuse_tree: bool | None = None, evaluator=None, window_size: int = 25,
                 reconcile: bool | None = None, auto_advance: bool = False):
        """``reuse_tree=None`` RESOLVES FROM ``cfg`` — the same line
        ``HeuristicPriorAgent.__init__`` runs (``bool(cfg.reuse_tree) if reuse_tree is
        None else bool(reuse_tree)``), and it is load-bearing: the production
        clairvoyant config carries ``reuse_tree=True``, so a class that defaulted to
        False would silently CLEAR where the Python champion RE-ROOTS. (Caught by
        `gate_clair_backend.py` at ply 1 of the first game: python root_n 48 = 24
        carried + 24 new, rust root_n 24.) A single-move gate cannot see this — a fresh
        agent has nothing to re-root into — which is why the full-game leg exists."""
        import carc_rs

        if evaluator is not None:
            raise ValueError(
                "evaluator injection has no carc_rs implementation (the Rust core "
                "carries no net — Gap 3 of BACKEND_BYPASS_AUDIT_20260801 §3). "
                "Build this ruler with backend='python'.")
        self._game = game
        self._cfg = cfg
        self._sims = int(simulations)
        # Gap 1: recorded, and PROVEN inert at these knobs
        # (measurement/rustport_p6/GAP1_SEED_INVARIANCE.json). The seed feeds
        # NeuralMCTS._np_rng, which only temperature sampling and Dirichlet root
        # noise consume — neither is engaged on this path.
        self._seed = seed
        self._reuse_tree = (bool(getattr(cfg, "reuse_tree", False))
                            if reuse_tree is None else bool(reuse_tree))
        self._auto_advance = bool(auto_advance)
        self._reconcile = reconcile_enabled(reconcile)
        self._scfg = search_config_rs(cfg, self._sims)
        self._carc_rs = carc_rs
        self._window_size = _resolve_mirror_window(game, window_size)
        # F9-A0, same hole and same fix as RustClairvoyantAgent (see
        # `mirror_geometry_kwargs`): `{}` under `walled`.
        self._geom = mirror_geometry_kwargs(game)
        self._mirror_preplaces = (self._geom.get("start_rule") == "retail")
        self._ps = None
        self._started = False
        self._plies = 0
        self._moves = 0
        self._last = None
        self.total_secs = 0.0
        self.prefix_moves = 0
        self.prefix_secs = 0.0
        # HeuristicPriorAgent's own re-root bookkeeping, same names.
        self.reuse_hits = 0
        self.reuse_fresh = 0
        self.reuse_collide = 0
        self.heur_moves = 0
        self.latch_k = None

    # --- lifecycle ---------------------------------------------------------- #
    def _open(self, mirror) -> None:
        self._ps = self._carc_rs.PersistentSearcher(mirror, self._scfg)
        self._started = True
        self._plies = self._moves = 0
        self.total_secs = self.prefix_secs = 0.0
        self.prefix_moves = 0

    def start_game(self, board) -> None:
        """Seat on an INITIAL board, using the deck it was dealt (draw order)."""
        st = board.state
        if st.next_tile is None:
            raise ValueError("start_game needs an INITIAL board (next_tile is None)")
        descs = _draw_order_for_mirror(st, self._mirror_preplaces)
        self._open(self._carc_rs.MirrorState.from_deck(
            descs, window_size=self._window_size, **self._geom))
        self.check_sync(board, "start_game")   # unconditional at ply 0 — see above

    def start_game_from_seed(self, deck_seed: int | str) -> None:
        self._open(self._carc_rs.MirrorState.from_seed(
            str(deck_seed), window_size=self._window_size, **self._geom))

    def seat(self, deck_seed: int | str, prefix, board=None) -> None:
        """Seat MID-GAME: ``from_seed(deck_seed)`` + ``advance`` over ``prefix``.

        The byte-equal counterpart of ``root_replay.replay_actions`` (which is
        ``random.seed(deck_seed); Game().get_init_board()`` + the same actions),
        and the same construction ``rust_world_search.RustWorldSearcher`` uses.
        Pass ``board`` to have the seating PROVED rather than assumed.
        """
        ms = self._carc_rs.MirrorState.from_seed(
            str(int(deck_seed)), window_size=self._window_size, **self._geom)
        n = 0
        for a in prefix:
            ms.advance(int(a))
            n += 1
        self._open(ms)
        self._plies = n
        if board is not None:
            self.check_sync(board, f"seat(ply {n})")

    def set_unseen_deck(self, descriptions) -> None:
        """Install one determinization world's deck (``set_unseen_deck``).

        Does NOT touch the retained tree — matching Python, where the world is a
        property of the BOARD the agent is handed and the agent's ``_nodes`` is
        untouched by it. In the pilot's playout the world is installed once,
        before the first search, so the retained tree is always a tree of THIS
        world.
        """
        self._ps.set_unseen_deck([str(d) for d in descriptions])

    def set_world(self, world_board) -> None:
        """``set_unseen_deck`` from an already-determinized Python board."""
        self.set_unseen_deck([t.description for t in world_board.state.deck])

    def close(self) -> None:
        """No-op — the Rust ruler owns no processes. Present for drop-in parity."""

    # --- the mirror choke point --------------------------------------------- #
    def advance(self, action: int, board_after=None) -> None:
        if not self._started:
            raise RuntimeError("advance before start_game()/seat()")
        self._ps.advance(int(action))
        self._plies += 1
        if board_after is not None:
            self._check_sync(board_after, f"advance({action})")

    def clear(self) -> None:
        """``NeuralMCTS.clear()`` — drop the retained tree, keep the mirror."""
        if self._ps is not None:
            self._ps.clear()

    # --- the two decisions --------------------------------------------------- #
    def best_action(self, board) -> int:
        """``HeuristicPriorAgent.best_action`` — search on the CARRIED tree."""
        return self._decide(board, "carry")

    def move(self, board) -> int:
        """``HeuristicPriorAgent.move`` — clear (or re-root), then ``best_action``."""
        self.neural_moves += 1
        return self._decide(board, "reroot" if self._reuse_tree else "fresh")

    def _decide(self, board, how: str) -> int:
        if not self._started:
            self.start_game(board)
        # Unconditional, for the same reason RustFairAgent's is: a caller that
        # forgets to advance would otherwise be answered from a frozen mirror.
        self.check_sync(board, f"{how}_search")
        t0 = time.perf_counter()
        if how == "carry":
            res = self._ps.search()
        elif how == "fresh":
            res = self._ps.search_fresh()
        else:
            res = self._ps.search_reroot()
            tag = res.get("reroot")
            if tag == "hit":
                self.reuse_hits += 1
            elif tag == "collide":
                self.reuse_collide += 1
            else:
                self.reuse_fresh += 1
        dt = time.perf_counter() - t0
        self.total_secs += dt
        self.prefix_secs += dt
        self.prefix_moves += 1
        self._moves += 1
        self._last = res
        action = int(res["chosen_action"])
        if self._auto_advance:
            self._ps.advance(action)
            self._plies += 1
        return action

    # --- reconcile ----------------------------------------------------------- #
    def _check_sync(self, board, where: str) -> None:
        if not self._reconcile:
            return
        self.check_sync(board, where)

    def check_sync(self, board, where: str = "check_sync") -> None:
        want = self._game.string_representation(board)
        got = self._ps.string_repr()
        if want == got:
            return
        raise MirrorDesync(
            f"rust carry-clairvoyant mirror desync at {where} (ply {self._plies}): "
            f"python digest {_short(want)} != rust digest {_short(got)}\n"
            f"  python: {want[:400]}\n  rust  : {got[:400]}")

    # --- read-off ------------------------------------------------------------ #
    def last_search(self) -> dict:
        """The last search's raw surface (floats as raw f64 BITS) — the G3 shape,
        plus the carry diagnostics (``root_n_before`` / ``carried`` / ``tree_len``
        / ``reroot``)."""
        return dict(self._last)

    def tree_len(self) -> int:
        return int(self._ps.tree_len())

    def root_n(self) -> int:
        """The CURRENT position's retained visit count (0 = not in the tree) —
        the GAP2 measurement's ``pre.N``."""
        return int(self._ps.root_n())

    def string_repr(self) -> str:
        return self._ps.string_repr()

    def stats(self) -> dict:
        return {
            "backend": "rust",
            "agent_class": "RustCarryClairvoyantAgent",
            "neural_moves": int(self.neural_moves),
            "moves": int(self._moves),
            "prefix_moves": int(self.prefix_moves),
            "prefix_secs": float(self.prefix_secs),
            "total_secs": float(self.total_secs),
            "ms_per_move": (1e3 * self.total_secs / self._moves
                            if self._moves else 0.0),
            "simulations": int(self._sims),
            "seed": self._seed,
            "seed_note": "inert at these knobs — proven by "
                         "measurement/rustport_p6/GAP1_SEED_INVARIANCE.json",
            "reuse_tree": bool(self._reuse_tree),
            "auto_advance": bool(self._auto_advance),
            "tree_policy": "persistent (carc_rs.PersistentSearcher) — best_action "
                           "carries, move() clears or re-roots",
            "reuse_hits": int(self.reuse_hits),
            "reuse_fresh": int(self.reuse_fresh),
            "reuse_collide": int(self.reuse_collide),
            "tree_nodes": (int(self._ps.tree_len()) if self._ps is not None else 0),
            "reconcile": bool(self._reconcile),
            "plies_advanced": int(self._plies),
        }

    def __repr__(self) -> str:
        return (f"RustCarryClairvoyantAgent(sims={self._sims}, seed={self._seed}, "
                f"reuse_tree={self._reuse_tree}, auto_advance={self._auto_advance})")
