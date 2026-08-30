"""OM-M1 — refutation-priced arbitration, the first kill-gate's shared spine.

⛔ **INSTRUMENT ONLY.** Spec of record:
``measurement/omm1_refuter_gate_20260830/PREREG.md``. Nothing here may enter
``governance/PRODUCTION.yaml``, ``CHECKPOINT_LINEAGE.csv`` or any adoption
chain — the refuter is asymmetric by construction and carries the same status
as the shape-B invader leaf it reuses
(``measurement/invasion_screen_r3_prep/screen_lib.SHAPE_B_IS_AN_INSTRUMENT_NOT_A_CANDIDATE``).

Everything a reader has to trust twice lives here rather than in the three
entry points, so the prereg's constants have exactly ONE definition each.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

SCHEMA = "carcassonne-omm1-refuter-gate/v1"

#: PREREG §4 / `G-SALT`. Any other value is a different experiment
#: (`carc_core::tiearb::TIEARB_SALT_OF_RECORD`'s own doc rule).
SALT_OF_RECORD = "tiearb2-deploy-v1"
ARM_CAP_J = 4
EPS = 0.0
MAX_PLIES = 400

#: PREREG §4.2. The gate runs at B=64; the DEPLOYED B=16 arbitration is the
#: first 16 of those worlds bit-exactly (the world seed does not depend on B —
#: pinned by `tiearb::tests::a_wider_run_contains_the_narrower_one_world_for_world`).
B_WORLDS = 64
B_DEPLOYED = 16
#: The world index at which the two-leg split happens: worlds [0, SPLIT) are the
#: symmetric half, [SPLIT, B) the refuter/placebo half.
SPLIT = B_WORLDS // 2

#: The leg seed suffix that gives P / R_ref / R_max their OWN playout stream.
#: The symmetric leg's suffix is EMPTY, which is what makes it bit-identical to
#: the deployed `arbitrate` (`G-BITEXACT`).
LEG2_SUFFIX = ["omm1-leg2"]

LEG_SYM = "S"
LEG_PLACEBO = "P"
LEG_REF = "R_ref"
LEG_MAX = "R_max"

#: PREREG §2 — the banked constants the bar is derived from.
#: `G_arb`: the deployed ARB-vs-RND transfer, +3.0700 pts/game at n=800
#: deck-paired, z +4.445 (`measurement/tiearb2_stage2_20260817/READOUT.md`).
G_ARB_PTS_PER_GAME = 3.0700
#: `A_bar`: mean arms per fired ply
#: (`tiearb2_20260816/corpus/positions/POSITIONS_PLAN.json::mean_arms`).
MEAN_ARMS = 3.0022
#: PREREG §5: half of CL-083's registered >= 2 pts/game falsifier bar.
TARGET_PTS_PER_GAME = 1.0

#: ⭐ The fraction of FIRED plies at which ARB and RND pick differently: RND
#: draws uniformly among `MEAN_ARMS` arms, ARB takes the argmax.
P_ARB_NE_RND = 1.0 - 1.0 / MEAN_ARMS


def bar_delta_flip() -> float:
    """PREREG §5's bar, derived — and **the fire rate cancels out of it**.

    The naive form is `target / (F * R_x)` where `R_x` is points per changed
    tied-arm pick. But `R_x` is itself `G_arb / (F * P_ARB_NE_RND)`, so::

        bar = target / (F * G_arb / (F * P)) = target * P / G_arb

    `F` appears in both the numerator and the denominator and cancels exactly.
    That matters here, because the `22.96 fired tile plies/game` figure quoted
    in the tiearb plans is the **E4 stratum** (597 tied plies / 26 phone games,
    `tiletie_pricing_20260812/DESIGN.md:792`), NOT the walled champion-selfplay
    corpora this gate replays — whose own banked census reads **45.26
    exact-tied tile plies/game** (`tiearb_widening_20260817/census/tile_gap_rows.jsonl`,
    20,322/31,827 = 63.9% over 449 games). A bar that depended on `F` would
    have been wrong by ~2x. This one does not.

    ⚠️ The one thing that does NOT cancel: the flip rate measured on THIS
    population is assumed to transfer to the population `G_arb` was measured on.
    Stated as a limitation in PREREG §3, not papered over.
    """
    return TARGET_PTS_PER_GAME * P_ARB_NE_RND / G_ARB_PTS_PER_GAME


#: PREREG §5, FROZEN. `1.0 * 0.6669 / 3.0700 = 0.21723`, rounded UP to 0.22.
#: NOT 2 sigma-hat of the instrument (~0.035 at the planned n) — the house rule
#: adopted 2026-08-30 forbids that.
BAR_DELTA_FLIP = 0.22
#: PREREG §5 conjunct: at least this fraction of primary flips must reproduce
#: under the leg-half swap.
BAR_SWAP_REPLICATION = 0.50

#: Points per changed tied-arm pick, on the walled corpora's own fire rate.
#: REPORTING ONLY — `bar_delta_flip()` never uses it (see above).
FIRED_PLIES_PER_GAME_WALLED = 45.26
R_X_PTS_PER_CHANGED_PICK = G_ARB_PTS_PER_GAME / (
    FIRED_PLIES_PER_GAME_WALLED * P_ARB_NE_RND
)

#: PREREG §7 `G-FIRE`, the RATE half. The deployed trigger fires at a SUBSET of
#: the exact-tied tile plies (arm dedupe collapses some tie sets to one arm), so
#: the replayed rate must be a sane fraction of the banked 45.26/game. The
#: decisive half of `G-FIRE` is the per-ply JOIN below, not this bracket.
BANKED_TIED_TILE_PLIES_PER_GAME = 45.26
FIRE_RATE_FRACTION_BRACKET = (0.60, 1.00)

#: The banked per-ply tie census the frame is joined against (`G-FIRE`, exact
#: half). Tracked, `champ449` only — 31,827 TILE rows carrying `tie_exact`.
TILE_CENSUS = (
    REPO / "measurement" / "tiearb_widening_20260817" / "census" / "tile_gap_rows.jsonl"
)

#: PREREG §7 `G-LEAF`.
LEAF_HASH_OF_RECORD = "a36d2e15a3b3d71d"

#: PREREG §3. Adjudication is on the POOLED row; the split is diagnostic.
CORPORA = (
    ("champ449", REPO / "measurement" / "champ_action_logs" / "champ_games.jsonl"),
    (
        "tiearb2_850",
        REPO / "measurement" / "tiearb2_20260816" / "corpus" / "champ_games_tiearb2.jsonl",
    ),
)

#: BLIND DISCIPLINE (the widening census's rule, inherited). The only keys this
#: instrument may read out of a corpus record. `score_p0`/`score_p1` are outcome
#: fields and are deliberately absent: the gate never sees who won.
_GAME_FIELDS_READ = ("game_id", "deck_seed", "actions", "n_plies")

OUT_DIR = REPO / "measurement" / "omm1_refuter_gate_20260830"


# --------------------------------------------------------------------------- #
# refuter doses (PREREG §4.2 / §4.3)                                           #
# --------------------------------------------------------------------------- #
#: `R_ref` — the shape-B invader OPPONENT OF RECORD.
#: `measurement/invasion_screen_r3_prep/DESIGN.md`: the C-arm ENV opponent runs
#: `CARCASSONNE_INVASION_ALPHA=0.09`, `CARCASSONNE_INVASION_ALPHA_CAP=11.0`
#: (resolved leaf `42adadc988784b44`). Round 2 demoted shape B as a CANDIDATE;
#: round 3 kept it as an INSTRUMENT, which is exactly the status this gate needs.
REFUTER_OF_RECORD = {
    "invasion_alpha": 0.09,
    "invasion_alpha_cap": 11.0,
    "invasion_stub_max_tiles": 2,
}

#: `R_max` — the expression CEILING, and the arm the kill is adjudicated on
#: (PREREG §6.1). `invasion_beta = 1.0` has the exact stated meaning "a
#: contestable component is worth nothing in the differential"
#: (`carc_core::leaf::invasion::shape_a_term` docs); alpha at 1.0 lets the
#: stub-merge potential reach its cap in POINTS rather than in hundredths of a
#: point, which the int64 rollout scorer's granularity otherwise swamps.
REFUTER_MAX = {
    "invasion_alpha": 1.0,
    "invasion_alpha_cap": 11.0,
    "invasion_stub_max_tiles": 2,
    "invasion_beta": 1.0,
}


def stable_seed(*parts) -> int:
    """`sha256("|".join(parts))` -> non-negative int.

    The house discipline (`carc_core::tiearb::seed_i64`,
    `build_positions._stable_seed`): never `random.Random(<tuple>)`, whose hash
    is per-process salted, and always a `"|"`-join so two different part lists
    cannot collide by concatenation.
    """
    joined = "|".join(str(p) for p in parts)
    return int.from_bytes(hashlib.sha256(joined.encode()).digest()[:8], "big") & 0x7FFFFFFFFFFFFFFF


def load_games(path: Path, corpus: str) -> list[dict]:
    """Corpus records, restricted to `_GAME_FIELDS_READ` (blind discipline)."""
    if not path.exists():
        raise FileNotFoundError(
            f"corpus {corpus!r} not found at {path}. PREREG §3 names two corpora and "
            "adjudicates on the POOLED row; a missing one is a DEVIATION that must be "
            "recorded, not silently dropped."
        )
    out = []
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            out.append({k: rec[k] for k in _GAME_FIELDS_READ if k in rec} | {"corpus": corpus})
    return out


def leaf_of_record():
    """`(LeafConfigRs, leaf_hashes)` for the champion leaf, `G-LEAF`-verified.

    Must be called only AFTER the rules env is exported — `champion_factory`
    latches R9 into a Rust `OnceLock` at import.
    """
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import leaf_config_rs

    cfg = CF.production_leaf_cfg()
    CF.verify_leaf(cfg)
    hashes = dict(CF.resolved_manifest("clairvoyant", verify=True).get("leaf_hashes") or {})
    got = hashes.get("harness_leaf_hash")
    if got != LEAF_HASH_OF_RECORD:
        raise AssertionError(
            f"G-LEAF: resolved harness_leaf_hash={got!r}, expected {LEAF_HASH_OF_RECORD!r}"
        )
    return leaf_config_rs(cfg), hashes


def refuter_leaf_rs(overrides: dict):
    """The champion leaf with ONLY the named invasion fields overridden.

    Built off `production_leaf_cfg()` so the refuter differs from the champion
    leaf in exactly the fields PREREG §4.2 names and in nothing else — the
    `G-LEAF` half that a hand-rolled LeafConfig could not promise.
    """
    from carcassonne_ai import champion_factory as CF
    from carcassonne_ai.rust_agent import leaf_config_rs

    cfg = CF.production_leaf_cfg()
    for k, v in overrides.items():
        if not hasattr(cfg, k):
            raise AttributeError(
                f"{k!r} is not a LeafConfig field — a typo here would silently ship an "
                "UNARMED refuter and the gate would read a structural zero."
            )
        setattr(cfg, k, v)
    return leaf_config_rs(cfg)


def leg_specs(include_ref: bool = True, include_max: bool = True) -> list[tuple]:
    """The four legs of PREREG §4.2, in the frozen order S, P, R_ref, R_max.

    Order is load-bearing only for readability — every statistic addresses legs
    by NAME — but it is frozen so two runs' raw files line up.
    """
    legs = [
        (LEG_SYM, [], None),
        (LEG_PLACEBO, list(LEG2_SUFFIX), None),
    ]
    if include_ref:
        legs.append((LEG_REF, list(LEG2_SUFFIX), refuter_leaf_rs(REFUTER_OF_RECORD)))
    if include_max:
        legs.append((LEG_MAX, list(LEG2_SUFFIX), refuter_leaf_rs(REFUTER_MAX)))
    return legs


def prepare_env(profile: str = "walled") -> dict:
    """Export the import-latched rules env BEFORE any `carcassonne_ai` import.

    Same two-step order as `scripts/tiletie/chain_census.prepare_env`: rules env
    first (`match.export_profile_env`), then the production leaf env. The
    corpora of PREREG §3 are both `walled`.
    """
    import sys

    # `match` lives in scripts/jcz_match, `env_preamble` (the leaf env) in
    # scripts/human_anchor — the same path set `mine_disagreements` installs.
    for p in (
        REPO / "scripts",
        REPO / "scripts" / "jcz_match",
        REPO / "scripts" / "human_anchor",
    ):
        if str(p) not in sys.path and p.exists():
            sys.path.insert(0, str(p))
    import match as JM  # noqa: E402  stdlib-only at module level

    env = JM.export_profile_env(profile)
    import env_preamble  # noqa: F401,E402  leaf env

    return {**env, "leaf_env": dict(env_preamble.RESOLVED), "rules_profile": profile}


def manifest(extra: dict | None = None) -> dict:
    """The self-describing config every artifact carries (house rule)."""
    m = {
        "schema": SCHEMA,
        "spec": "measurement/omm1_refuter_gate_20260830/PREREG.md",
        "instrument_only": True,
        "salt": SALT_OF_RECORD,
        "arm_cap_j": ARM_CAP_J,
        "eps": EPS,
        "max_plies": MAX_PLIES,
        "b_worlds": B_WORLDS,
        "b_deployed": B_DEPLOYED,
        "split": SPLIT,
        "leg2_suffix": LEG2_SUFFIX,
        "refuter_of_record": REFUTER_OF_RECORD,
        "refuter_max": REFUTER_MAX,
        "bar_delta_flip": BAR_DELTA_FLIP,
        "bar_swap_replication": BAR_SWAP_REPLICATION,
        "bar_derivation": {
            "target_pts_per_game": TARGET_PTS_PER_GAME,
            "G_arb_pts_per_game": G_ARB_PTS_PER_GAME,
            "mean_arms": MEAN_ARMS,
            "p_arb_ne_rnd": P_ARB_NE_RND,
            "formula": "bar = target * (1 - 1/mean_arms) / G_arb  [the fire rate cancels]",
            "derived": bar_delta_flip(),
            "R_x_pts_per_changed_pick_reporting_only": R_X_PTS_PER_CHANGED_PICK,
            "fired_plies_per_game_walled": FIRED_PLIES_PER_GAME_WALLED,
        },
        "host": os.uname().nodename,
    }
    if extra:
        m.update(extra)
    return m
